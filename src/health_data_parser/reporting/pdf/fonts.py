from functools import cache
import sys

from reportlab.pdfbase import pdfmetrics, ttfonts

from health_data_parser.utils.logger import setup_logger

logger = setup_logger('pdf_fonts')

# (regular, bold) as (font name, TrueType file) per platform
_PLATFORM_FONTS = {
    "darwin": (("MesloLGS NF", "MesloLGS NF Regular.ttf"), ("MesloLGS NF Bold", "MesloLGS NF Bold.ttf")),
    "win32": (("arial", "arial.ttf"), ("arial bold", "arialbd.ttf")),
}
# reportlab's built-in fonts, available everywhere without registration. They
# cover Latin-1/WinAnsi text only.
BUILT_IN_FONTS = ("Helvetica", "Helvetica-Bold")


@cache
def report_fonts():
    """(regular, bold) font names for the report, registering the platform's
    TrueType fonts on first use and falling back to the built-in Helvetica
    family when they aren't available."""
    fonts = _PLATFORM_FONTS.get(sys.platform)
    if fonts is not None:
        try:
            for name, filename in fonts:
                pdfmetrics.registerFont(ttfonts.TTFont(name, filename))
            return fonts[0][0], fonts[1][0]
        except Exception as e:
            logger.warning(f"Report fonts {[f[1] for f in fonts]} not available ({e}); using Helvetica.")
    return BUILT_IN_FONTS


def regular_font():
    return report_fonts()[0]


def bold_font():
    return report_fonts()[1]
