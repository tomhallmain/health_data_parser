import array
import builtins
import struct

import pytest

from health_data_parser.analysis.summary import summary_lines
from health_data_parser.utils import translations
from health_data_parser.utils.translations import I18N, _


def write_mo(path, messages):
    """A gettext catalog (.mo) for `messages`, in the layout msgfmt produces."""
    messages = {"": "Content-Type: text/plain; charset=UTF-8\n", **messages}
    ids = strs = b""
    entries = []
    for key in sorted(messages):
        key_bytes, value_bytes = key.encode("utf-8"), messages[key].encode("utf-8")
        entries.append((len(ids), len(key_bytes), len(strs), len(value_bytes)))
        ids += key_bytes + b"\0"
        strs += value_bytes + b"\0"
    key_start = 7 * 4 + 16 * len(entries)
    value_start = key_start + len(ids)
    key_offsets, value_offsets = [], []
    for key_offset, key_length, value_offset, value_length in entries:
        key_offsets += [key_length, key_offset + key_start]
        value_offsets += [value_length, value_offset + value_start]
    header = struct.pack("Iiiiiii", 0x950412de, 0, len(entries), 7 * 4, 7 * 4 + len(entries) * 8, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + array.array("i", key_offsets + value_offsets).tobytes() + ids + strs)


@pytest.fixture
def restore_i18n():
    saved = (I18N.localedir, I18N.locale, I18N.translate)
    had_builtin = hasattr(builtins, "_")
    saved_builtin = getattr(builtins, "_", None)
    yield
    I18N.localedir, I18N.locale, I18N.translate = saved
    # install() sets builtins._
    if had_builtin:
        builtins._ = saved_builtin
    elif hasattr(builtins, "_"):
        del builtins._


class TestLanguageDetection:
    @pytest.mark.parametrize("value, expected", [
        ("de_DE.UTF-8", "de"), ("pt_BR", "pt"), ("en", "en"), ("sr@latin", "sr"),
        ("C", None), ("C.UTF-8", None), ("English_United States", None), ("", None), (None, None),
    ])
    def test_language_code(self, value, expected):
        assert translations._language_code(value) == expected

    def test_lang_variable(self, monkeypatch):
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        assert translations._user_language() == "fr"

    def test_platform_locale_without_lang(self, monkeypatch):
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.setattr(translations.locale, "getlocale", lambda: ("de_DE", "UTF-8"))
        assert translations._user_language() == "de"

    def test_english_when_nothing_usable(self, monkeypatch):
        monkeypatch.delenv("LANG", raising=False)
        # Windows reports locale names rather than language codes
        monkeypatch.setattr(translations.locale, "getlocale", lambda: ("English_United States", "1252"))
        assert translations._user_language() == "en"


class TestI18N:
    def test_strings_pass_through_without_a_catalog(self):
        assert _("Some text that has no translation") == "Some text that has no translation"

    def test_missing_catalog_falls_back(self, restore_i18n, tmp_path):
        I18N.localedir = str(tmp_path)
        I18N.install_locale("de", verbose=False)
        assert I18N.locale == "de"
        assert _("All Lab Observations") == "All Lab Observations"

    def test_installed_catalog_is_used_at_call_time(self, restore_i18n, tmp_path):
        write_mo(tmp_path / "de" / "LC_MESSAGES" / "base.mo",
                 {"All Lab Observations": "Alle Laborbefunde", "Abnormal Results: {0}": "Auffällige Ergebnisse: {0}"})
        I18N.localedir = str(tmp_path)

        I18N.install_locale("de", verbose=False)

        assert _("All Lab Observations") == "Alle Laborbefunde"
        # Modules that imported _ before the switch translate with the new catalog
        assert "Auffällige Ergebnisse: 0" in summary_lines({})
