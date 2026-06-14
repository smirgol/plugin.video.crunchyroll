"""
Focused unit tests for resources.lib.models.base

Covers Object._read and Cacheable storage round-trips.
"""

import os

from resources.lib.globals import G
from resources.lib.models.base import Cacheable, Object


class TestObjectRead:
    def test_first_key_exists(self):
        assert Object._read({"a": 1, "b": 2}, "a", "b") == 1

    def test_second_key_exists(self):
        assert Object._read({"b": 2}, "a", "b") == 2

    def test_no_key_exists(self):
        assert Object._read({"c": 3}, "a", "b") is None

    def test_empty_data(self):
        assert Object._read({}, "a") is None


class ConcreteCacheable(Cacheable):
    def get_cache_file_name(self) -> str:
        return "test_cache.json"


class TestCacheableRoundTrip:
    def test_storage_roundtrip(self, tmp_path, monkeypatch):
        import xbmcvfs

        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        G.args.addon.getAddonInfo.return_value = str(profile_dir)
        monkeypatch.setattr(xbmcvfs, "translatePath", lambda p: str(profile_dir) + os.sep)

        class RealFile:
            def __init__(self, path, mode="r"):
                self._f = open(path, mode)

            def __enter__(self):
                return self._f

            def __exit__(self, *args):
                self._f.close()

        monkeypatch.setattr(xbmcvfs, "File", RealFile)
        monkeypatch.setattr(xbmcvfs, "exists", os.path.exists)
        monkeypatch.setattr(xbmcvfs, "delete", os.remove)

        obj = ConcreteCacheable()
        obj.field_a = "hello"
        obj.field_b = 42

        written = obj.write_to_storage()
        assert written is not False
        assert (profile_dir / "test_cache.json").exists()

        loaded = obj.load_from_storage()
        assert loaded["field_a"] == "hello"
        assert loaded["field_b"] == 42

        obj.delete_storage()
        assert not (profile_dir / "test_cache.json").exists()

    def test_load_from_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        import xbmcvfs

        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        G.args.addon.getAddonInfo.return_value = str(profile_dir)
        monkeypatch.setattr(xbmcvfs, "translatePath", lambda p: str(profile_dir) + os.sep)
        monkeypatch.setattr(xbmcvfs, "exists", lambda p: False)

        obj = ConcreteCacheable()
        assert obj.load_from_storage() == {}

    def test_delete_missing_file_returns_none(self, tmp_path, monkeypatch):
        import xbmcvfs

        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()

        G.args.addon.getAddonInfo.return_value = str(profile_dir)
        monkeypatch.setattr(xbmcvfs, "translatePath", lambda p: str(profile_dir) + os.sep)
        monkeypatch.setattr(xbmcvfs, "exists", lambda p: False)

        obj = ConcreteCacheable()
        assert obj.delete_storage() is None
