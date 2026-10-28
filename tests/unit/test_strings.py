"""
Checks for localized strings in resources/language/*/strings.po.
"""

import re
from pathlib import Path

import pytest

LANGUAGE_DIR = Path(__file__).parent.parent.parent / "resources" / "language"
LANGUAGES = ["en_gb", "de_de", "es_es", "fr_fr", "pt_br"]


def _entry(language, string_id):
    content = (LANGUAGE_DIR / f"resource.language.{language}" / "strings.po").read_text(encoding="utf-8")
    match = re.search(
        rf'^msgctxt "#{string_id}"\nmsgid "(?P<msgid>[^"]*)"\nmsgstr "(?P<msgstr>[^"]*)"$',
        content,
        re.MULTILINE,
    )
    return match


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_matching_version_string_present(language):
    entry = _entry(language, 30091)

    assert entry is not None, f"#30091 missing in {language}"
    assert entry.group("msgid") == "No matching language version available"


def test_no_matching_version_string_english_text():
    assert _entry("en_gb", 30091).group("msgstr") == "No matching language version available"


def test_no_matching_version_string_german_text():
    assert _entry("de_de", 30091).group("msgstr") == "Keine passende Sprachversion verfügbar"


NEXT_EPISODE_STRINGS = {
    30500: {
        "en_gb": "Offer next episode after playback",
        "de_de": "Nächste Folge nach dem Ende anbieten",
        "es_es": "Ofrecer el siguiente episodio al terminar",
        "fr_fr": "Proposer l'épisode suivant à la fin",
        "pt_br": "Oferecer o próximo episódio ao terminar",
    },
    30501: {
        "en_gb": "Countdown until next episode (seconds)",
        "de_de": "Countdown bis zur nächsten Folge (Sekunden)",
        "es_es": "Cuenta atrás hasta el siguiente episodio (segundos)",
        "fr_fr": "Compte à rebours avant l'épisode suivant (secondes)",
        "pt_br": "Contagem regressiva até o próximo episódio (segundos)",
    },
    30502: {
        "en_gb": "Up next",
        "de_de": "Als Nächstes",
        "es_es": "A continuación",
        "fr_fr": "À suivre",
        "pt_br": "A seguir",
    },
    30503: {
        "en_gb": "Continue",
        "de_de": "Weiter",
        "es_es": "Continuar",
        "fr_fr": "Continuer",
        "pt_br": "Continuar",
    },
    30504: {
        "en_gb": "Cancel",
        "de_de": "Abbrechen",
        "es_es": "Cancelar",
        "fr_fr": "Annuler",
        "pt_br": "Cancelar",
    },
    30505: {
        "en_gb": "Starts in %d s",
        "de_de": "Startet in %d s",
        "es_es": "Empieza en %d s",
        "fr_fr": "Commence dans %d s",
        "pt_br": "Começa em %d s",
    },
    30506: {
        "en_gb": "Are you still watching?",
        "de_de": "Schaust du noch?",
        "es_es": "¿Sigues viendo?",
        "fr_fr": "Vous regardez toujours ?",
        "pt_br": "Você ainda está assistindo?",
    },
    30507: {
        "en_gb": "Ask if still watching after automatic episodes (0 = off)",
        "de_de": "Nach automatischen Folgen nachfragen, ob du noch schaust (0 = aus)",
        "es_es": "Preguntar si sigues viendo tras episodios automáticos (0 = desactivado)",
        "fr_fr": "Demander si vous regardez toujours après des épisodes automatiques (0 = désactivé)",
        "pt_br": "Perguntar se ainda está assistindo após episódios automáticos (0 = desligado)",
    },
}
NEXT_EPISODE_IDS = sorted(NEXT_EPISODE_STRINGS)
NEXT_EPISODE_PAIRS = [(language, string_id) for language in LANGUAGES for string_id in NEXT_EPISODE_IDS]


@pytest.mark.parametrize(("language", "string_id"), NEXT_EPISODE_PAIRS)
def test_next_episode_strings_present(language, string_id):
    entry = _entry(language, string_id)

    assert entry is not None, f"#{string_id} missing in {language}"
    assert entry.group("msgid") == NEXT_EPISODE_STRINGS[string_id]["en_gb"]


@pytest.mark.parametrize(("language", "string_id"), NEXT_EPISODE_PAIRS)
def test_next_episode_strings_translated(language, string_id):
    entry = _entry(language, string_id)

    assert entry is not None, f"#{string_id} missing in {language}"
    assert entry.group("msgstr") == NEXT_EPISODE_STRINGS[string_id][language]


@pytest.mark.parametrize("language", LANGUAGES)
def test_countdown_format_has_single_int_placeholder(language):
    entry = _entry(language, 30505)

    assert entry is not None, f"#30505 missing in {language}"
    msgstr = entry.group("msgstr")
    assert msgstr.count("%d") == 1
    assert msgstr.count("%") == 1
    assert "15" in msgstr % 15


@pytest.mark.parametrize("language", LANGUAGES)
def test_still_watching_setting_label_says_zero_is_off(language):
    entry = _entry(language, 30507)

    assert entry is not None, f"#30507 missing in {language}"
    assert "(0 = " in entry.group("msgstr")


@pytest.mark.parametrize("language", LANGUAGES)
def test_next_episode_string_ids_unique(language):
    content = (LANGUAGE_DIR / f"resource.language.{language}" / "strings.po").read_text(encoding="utf-8")

    for string_id in NEXT_EPISODE_IDS:
        assert content.count(f'msgctxt "#{string_id}"') == 1, f"#{string_id} not exactly once in {language}"
