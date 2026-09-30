import gettext
import locale
import os
import re

from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.paths import repo_root

logger = setup_logger("translations")


def _language_code(value):
    """The language part of a locale name ("de_DE.UTF-8" -> "de"), or None
    when it isn't a language code (e.g. "C", or Windows' "English_United States")."""
    code = re.split(r"[_.@]", value or "", maxsplit=1)[0].lower()
    return code if re.fullmatch(r"[a-z]{2,3}", code) else None


def _user_language():
    """The language from LANG, else the platform locale, else English."""
    language = _language_code(os.environ.get("LANG"))
    if language is None:
        try:
            language = _language_code(locale.getlocale()[0])
        except ValueError:
            language = None
    return language or "en"


class I18N:
    localedir = os.path.join(repo_root(), 'locale')
    locale = _user_language()
    # With no catalog for the language, strings are shown as written
    translate = gettext.translation('base', localedir, languages=[locale], fallback=True)

    @staticmethod
    def install_locale(locale, verbose=True):
        I18N.locale = locale
        I18N.translate = gettext.translation('base', I18N.localedir, languages=[locale], fallback=True)
        I18N.translate.install()
        if verbose:
            logger.info("Switched locale to: " + locale)

    @staticmethod
    def _(s):
        try:
            return I18N.translate.gettext(s)
        except KeyError:
            return s


'''
NOTE when gathering the translation strings, set _() == to gettext.gettext() instead of the above, and run:

    ```python C:\\Python310\\Tools\\i18n\\pygettext.py -d base -o locale\\base.pot src```

in the base directory. The POT output file can be used as source for the PO files in each locale.
Run personal script C:\\Scripts\\i18n_manager.py to generate new PO files and look for invalid translations.

Then for each locale once the PO files are set up as desired, run below in the deepest locale directory to produce the MO file from the PO file:
    ```python C:\\Python310\\Tools\\i18n\\msgfmt.py -o base.mo base```
'''

_ = I18N._
