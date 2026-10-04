"""Exploration probe: which input decides the audio version the API returns?

Season and episode IDs exist per audio version (``versions[]``). With ``meta.versions_considered=true`` the API seems
to pick the returned version from request params / account preferences rather than from the passed ID. This probe
records raw responses for a small request matrix so that can be proven. It asserts nothing about API behaviour.

Run explicitly (real API calls, needs tests/.env). Without PROBE=1 the test is skipped before any fixture runs:

    PROBE=1 uv run pytest -m probe -s

Call budget (hard cap MAX_CALLS = 30, counted per real HTTP send via CloudScraper.perform_request):
    profile (default audio language)   1
    seasons V1..V5                      5
    episodes ja + de season x V1..V3    6
    objects                             1
    playback ja + de                    2   (separate hard cap MAX_PLAYBACK_CALLS = 2, retries included)
    stream release (DELETE) ja + de     2
    ---------------------------------------
    total                              17
Cloudflare challenge solving, 401 retries and token refreshes inside make_scraper_request use the same scraper and
are counted too. A token refresh inside the probe costs 3 calls (token POST + index + profile); it uses the args stub
for device_id, and the session write goes to the kodistubs no-op storage. The TokenManager refresh in the
``api_client`` fixture runs before the probe and is outside the budget.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from resources.lib.models.exceptions import CrunchyrollError, LoginError
from resources.modules.cloudscraper.exceptions import CloudflareException

MAX_CALLS = 30
MAX_PLAYBACK_CALLS = 2
MAX_MESSAGE_LENGTH = 300
SERIES_ID = os.getenv("PROBE_SERIES_ID", "GQWH0M1J3")
LOCALE = os.getenv("PROBE_LOCALE", "de-DE")
OUTPUT_FILE = Path(__file__).parent.parent / "fixtures" / "probe_responses.json"
SIGNING_PARAMS = ("Policy", "Signature", "Key-Pair-Id")
PLAYBACK_PATH = "/playback/v2/"

PARAM_VARIANTS = {
    "V1": {"locale": LOCALE},
    "V2": {"locale": LOCALE, "preferred_audio_language": "ja-JP"},
    "V3": {"locale": LOCALE, "preferred_audio_language": "de-DE"},
    "V4": {"locale": LOCALE, "force_locale": ""},
    "V5": {"locale": "en-US"},
}
EPISODE_VARIANTS = ("V1", "V2", "V3")


class ProbeAborted(Exception):
    pass


class CallBudget:
    """Wraps the scraper's ``perform_request`` so every real HTTP send is delayed, counted and checked for blocking.

    ``CloudScraper.request`` solves Cloudflare challenges internally by calling ``perform_request`` repeatedly, so
    wrapping at this level sees the initial 403 / challenge page and aborts before cloudscraper tries to solve it.
    """

    def __init__(self, max_calls: int, max_playback_calls: int):
        self.max_calls = max_calls
        self.max_playback_calls = max_playback_calls
        self.calls = 0
        self.playback_calls = 0
        self.aborted: str | None = None
        self.releasing = False

    def abort(self, reason: str) -> ProbeAborted:
        if not self.aborted:
            self.aborted = reason
        return ProbeAborted(self.aborted)

    def wrap(self, scraper):
        original_perform_request = scraper.perform_request

        def counted_perform_request(method, url, *args, **kwargs):
            self._before_call(url)
            response = original_perform_request(method, url, *args, **kwargs)
            self._check_response(response)
            return response

        scraper.perform_request = counted_perform_request
        return scraper

    def _before_call(self, url: str) -> None:
        # stream release must always go out, even after an abort or when the cap is reached
        if not self.releasing:
            if self.aborted:
                raise ProbeAborted(self.aborted)
            if self.calls >= self.max_calls:
                raise self.abort(f"call budget of {self.max_calls} exhausted")
            if PLAYBACK_PATH in url:
                if self.playback_calls >= self.max_playback_calls:
                    raise self.abort(f"playback budget of {self.max_playback_calls} exhausted")
                self.playback_calls += 1
        # also before the first call: the fixture's token refresh has just been sent
        time.sleep(4 + random.uniform(0, 3))
        self.calls += 1

    def _check_response(self, response) -> None:
        # Detection happens on the raw response, before cloudscraper solves a challenge and before
        # get_json_from_response turns it into "[403] ..." / "[429] ..." CrunchyrollError (or an IndexError for an
        # empty error body).
        content_type = response.headers.get("Content-Type", "")
        body_start = response.text[:2000] if "html" in content_type else ""
        if response.status_code in (403, 429):
            reason = f"HTTP {response.status_code}"
        elif response.headers.get("cf-mitigated"):
            reason = "Cloudflare cf-mitigated header"
        elif "Just a moment" in body_start or "challenge-platform" in body_start:
            reason = "Cloudflare challenge page"
        else:
            return
        # the release URL carries the stream token, so it is not named
        target = "stream release" if self.releasing else f"{response.request.method} {_strip_query(response.url)}"
        raise self.abort(f"{reason} on {target}")


def _strip_query(url: str) -> str:
    return url.split("?", 1)[0]


def _items(response: dict | None) -> list:
    if not response:
        return []
    return response.get("data") or response.get("items") or []


def _versions_map(versions: list | None) -> dict:
    return {v.get("audio_locale"): v.get("guid") for v in versions or []}


def _find_version(versions: list, audio_locale: str) -> dict | None:
    return next((v for v in versions if v.get("audio_locale") == audio_locale), None)


def _pick_ja_and_de(versions: list, kind: str, notes: dict) -> tuple:
    """ja-JP guid (fallback: original version, noted) and de-DE guid (None when absent, noted)."""
    ja = _find_version(versions, "ja-JP")
    if not ja:
        ja = next((v for v in versions if v.get("original")), None)
        if ja:
            notes[f"{kind}_ja_fallback_original"] = ja.get("audio_locale")
    de = _find_version(versions, "de-DE")
    if not de:
        notes[f"{kind}_de_missing"] = "no de-DE version - de side skipped"
    return (ja or {}).get("guid"), (de or {}).get("guid")


def _args_stub(device_id: str):
    """Minimal stand-in for the plugin Args on the token refresh path; getSetting("") keeps API tracing off."""
    return SimpleNamespace(
        device_id=device_id,
        addon=SimpleNamespace(getSetting=lambda _key: "", getAddonInfo=lambda _key: ""),
        addon_name="probe",
        get_arg=lambda _key, default=None: default,
    )


class Probe:
    def __init__(self, api, budget: CallBudget):
        self.api = api
        self.budget = budget
        self.collected: dict = {}
        self.errors: dict = {}
        self.notes: dict = {}
        self.secrets: set = set()

    def _secret_values(self) -> set:
        account = self.api.account_data
        return {s for s in (self.secrets | {account.access_token, account.refresh_token}) if s}

    def clean(self, text: str) -> str:
        """Strip query strings and known secrets from free text, capped for stdout / JSON."""
        text = re.sub(r"\?\S*", "", str(text))
        for secret in self._secret_values():
            text = text.replace(secret, "<redacted>")
        return text[:MAX_MESSAGE_LENGTH]

    def redact(self, value):
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items() if "token" not in k.lower()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, str):
            if value.startswith("http"):
                value = _strip_query(value)
            for secret in self._secret_values():
                value = value.replace(secret, "<redacted>")
        return value

    def _abort_from(self, error: Exception) -> ProbeAborted:
        # production code wraps ProbeAborted into LoginError("Unexpected error: ..."); keep the original reason
        if self.budget.aborted:
            return ProbeAborted(self.budget.aborted)
        return self.budget.abort(self.clean(f"{type(error).__name__}: {error}"))

    def get(self, key: str, url: str, params: dict, scraper: bool = False) -> dict | None:
        """Single recorded GET. Non-blocking API errors are recorded and yield None; blocking ones abort."""
        recorded_params = {k: v for k, v in params.items() if k not in SIGNING_PARAMS}
        try:
            if scraper:
                response = self.api.make_scraper_request(method="GET", url=url, params=dict(params), auto_refresh=True)
            else:
                response = self.api.make_request(method="GET", url=url, params=dict(params))
        except ProbeAborted:
            raise
        except CrunchyrollError as e:
            if self.budget.aborted:
                raise ProbeAborted(self.budget.aborted) from e
            self.errors[key] = self.clean(e)
            print(f"  ! {key}: {self.errors[key]}")
            return None
        except (LoginError, CloudflareException) as e:
            raise self._abort_from(e) from e
        except Exception as e:
            # unknown failure mode (e.g. IndexError for an empty error body) - stop rather than keep hammering
            raise self._abort_from(e) from e

        self.collected[key] = {"request": {"url": url, "params": recorded_params}, "response": response}
        return response

    def release_stream(self, episode_id: str, token: str) -> None:
        # the DELETE URL contains the stream token - never print or record it
        self.budget.releasing = True
        try:
            self.api.make_request(method="DELETE", url=self.api.STREAMS_ENDPOINT_CLEAR_STREAM.format(episode_id, token))
            print(f"  released stream for {episode_id}")
        except Exception as e:
            print(f"  ! failed to release stream for {episode_id}: {type(e).__name__}")
        finally:
            self.budget.releasing = False

    def write(self) -> None:
        meta = {
            "series_id": SERIES_ID,
            "locale": LOCALE,
            "calls": self.budget.calls,
            "playback_calls": self.budget.playback_calls,
            "aborted": self.clean(self.budget.aborted) if self.budget.aborted else None,
            "errors": self.errors,
            "notes": self.notes,
        }
        OUTPUT_FILE.write_text(
            json.dumps(self.redact({"_meta": meta, **self.collected}), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote {len(self.collected)} responses to {OUTPUT_FILE} ({self.budget.calls} HTTP calls)")


def _probe_default_audio_language(probe: Probe) -> str | None:
    print("\n== Profile ==")
    language = probe.api.account_data.default_audio_language
    if language:
        print(f"  account_data.default_audio_language = {language} (from conftest)")
        return language
    profile = probe.get("profile", probe.api.PROFILE_ENDPOINT, {})
    language = (profile or {}).get("preferred_content_audio_language")
    probe.notes["default_audio_language_source"] = "PROFILE_ENDPOINT (conftest AccountData has none)"
    print(f"  conftest AccountData has no default_audio_language; profile says {language}")
    return language


def _probe_seasons(probe: Probe) -> dict | None:
    print("\n== Seasons: request -> returned audio_locale / ids ==")
    first_v1 = None
    for variant, params in PARAM_VARIANTS.items():
        response = probe.get(f"seasons_{variant}", probe.api.SEASONS_ENDPOINT.format(SERIES_ID), params)
        seasons = _items(response)
        print(f"  {variant} {params} meta={(response or {}).get('meta')}")
        for season in seasons:
            print(
                f"    {season.get('id')} audio={season.get('audio_locale')} "
                f"subs={season.get('subtitle_locales')} versions={_versions_map(season.get('versions'))}"
            )
        if variant == "V1" and seasons:
            first_v1 = seasons[0]
    return first_v1


def _probe_episodes(probe: Probe, season_ids: dict) -> dict | None:
    """season_ids: label (ja/de) -> season guid. Returns the first V1 episode, preferring the ja season."""
    print("\n== Episodes: request -> returned audio_locale / ids ==")
    first_v1_episodes = {}
    for label, season_id in season_ids.items():
        for variant in EPISODE_VARIANTS:
            params = PARAM_VARIANTS[variant]
            response = probe.get(
                f"episodes_{season_id}_{variant}", probe.api.EPISODES_ENDPOINT.format(season_id), params
            )
            episodes = _items(response)
            returned = sorted({(e.get("audio_locale"), e.get("season_id")) for e in episodes}, key=str)
            first_id = episodes[0].get("id") if episodes else None
            print(
                f"  {label} season={season_id} {variant} -> (audio, season_id)={returned} "
                f"first={first_id} count={len(episodes)} meta={(response or {}).get('meta')}"
            )
            if variant == "V1" and episodes:
                first_v1_episodes[label] = episodes[0]
    return first_v1_episodes.get("ja") or next(iter(first_v1_episodes.values()), None)


def _probe_objects(probe: Probe, episode_ids: list) -> None:
    print("\n== Objects: request -> returned audio_locale / ids ==")
    response = probe.get(
        "objects",
        probe.api.OBJECTS_BY_ID_LIST_ENDPOINT.format(",".join(episode_ids)),
        {"locale": LOCALE, "ratings": "true"},
    )
    for obj in _items(response):
        metadata = obj.get("episode_metadata") or {}
        print(
            f"  requested in {episode_ids} -> id={obj.get('id')} type={obj.get('type')} "
            f"audio={metadata.get('audio_locale', obj.get('audio_locale'))} "
            f"versions={_versions_map(metadata.get('versions') or obj.get('versions'))}"
        )


def _probe_playback(probe: Probe, label: str, episode_id: str, audio_language: str | None) -> None:
    params = {"preferred_audio_language": audio_language, "force_locale": ""}
    response = probe.get(
        f"playback_{label}", probe.api.STREAMS_ENDPOINT_DRM_ANDROID_TV.format(episode_id), params, scraper=True
    )
    token = (response or {}).get("token")
    if token:
        probe.secrets.add(token)
    try:
        if response:
            print(
                f"  {label} requested={episode_id} {params} -> audioLocale={response.get('audioLocale')} "
                f"hardSubs={sorted((response.get('hardSubs') or {}).keys())} "
                f"subtitles={sorted((response.get('subtitles') or {}).keys())} "
                f"url={'yes' if response.get('url') else 'no'} "
                f"versions={_versions_map(response.get('versions'))} keys={sorted(response.keys())}"
            )
    finally:
        if token:
            probe.release_stream(episode_id, token)


def _run_matrix(probe: Probe) -> None:
    audio_language = _probe_default_audio_language(probe)

    first_season = _probe_seasons(probe)
    if not first_season:
        print("  no seasons returned for V1 - stopping")
        return
    ja_season, de_season = _pick_ja_and_de(first_season.get("versions") or [], "season", probe.notes)
    season_ids = {label: guid for label, guid in (("ja", ja_season), ("de", de_season)) if guid}
    if not season_ids:
        season_ids = {"first": first_season.get("id")}
        probe.notes["season_fallback"] = "first V1 season has no usable versions - using its own id"

    first_episode = _probe_episodes(probe, season_ids)
    if not first_episode:
        print("  no episodes returned for V1 - stopping")
        return
    ja_episode, de_episode = _pick_ja_and_de(first_episode.get("versions") or [], "episode", probe.notes)
    episode_ids = [e for e in (ja_episode, de_episode) if e]
    if not episode_ids:
        print("  first episode has no usable versions - stopping")
        return

    _probe_objects(probe, episode_ids)

    print("\n== Playback: request -> returned audioLocale ==")
    for label, episode_id in (("ja", ja_episode), ("de", de_episode)):
        if episode_id:
            _probe_playback(probe, label, episode_id, audio_language)
        else:
            print(f"  {label}: no episode id - skipped")


@pytest.mark.integration
@pytest.mark.probe
@pytest.mark.skipif(os.getenv("PROBE") != "1", reason="exploratory probe - run with PROBE=1 uv run pytest -m probe -s")
def test_probe_api_versions(api_client, test_credentials, monkeypatch):
    budget = CallBudget(MAX_CALLS, MAX_PLAYBACK_CALLS)
    original_create_scraper = api_client.auth_manager.create_auth_scraper

    def create_counted_scraper():
        scraper = original_create_scraper()
        return budget.wrap(scraper) if scraper else scraper

    monkeypatch.setattr(api_client.auth_manager, "create_auth_scraper", create_counted_scraper)
    # session-scoped api_client has args=None; the refresh path reads args.device_id
    monkeypatch.setattr(api_client, "args", _args_stub(test_credentials["device_id"]))

    probe = Probe(api_client, budget)
    try:
        _run_matrix(probe)
    except ProbeAborted as e:
        print(f"\n!! probe aborted: {probe.clean(e)}")
    finally:
        probe.write()

    assert probe.collected, "probe collected no responses"
