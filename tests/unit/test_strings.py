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
