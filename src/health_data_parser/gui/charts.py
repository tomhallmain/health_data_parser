"""Figures for the results tabs, built from observations.json data.

Standalone Figures (no pyplot), so each is freed with its canvas.
"""
from matplotlib.figure import Figure

from health_data_parser.analysis.summary import (
    abnormal_counts_by_interpretation, observation_counts_by_date, observation_counts_by_year)
from health_data_parser.utils.translations import _


def _no_data(ax, text):
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes)


def overview_figure(json_data):
    """Observations per year, and abnormal results per interpretation."""
    counts_by_year = observation_counts_by_year(json_data)
    abnormal_by_interpretation = abnormal_counts_by_interpretation(json_data)

    fig = Figure(figsize=(8, 8))
    ax1, ax2 = fig.subplots(2, 1)

    ax1.bar([year for year, count in counts_by_year], [count for year, count in counts_by_year])
    ax1.set_title(_("Observations by Year"))
    ax1.set_ylabel(_("Observations"))
    if not counts_by_year:
        _no_data(ax1, _("No observations"))

    ax2.bar([label for label, count in abnormal_by_interpretation],
            [count for label, count in abnormal_by_interpretation], color="tab:red")
    ax2.set_title(_("Abnormal Results by Interpretation"))
    ax2.set_ylabel(_("Results"))
    ax2.tick_params(axis="x", labelrotation=20)
    if not abnormal_by_interpretation:
        _no_data(ax2, _("No abnormal results"))

    fig.tight_layout()
    return fig


def trends_figure(json_data):
    """Observations per date, and abnormal results per date."""
    fig = Figure(figsize=(12, 8))
    fig.suptitle(_("Health Data Trends"))
    axes = fig.subplots(2, 1, sharex=True)

    plots = [
        (axes[0], observation_counts_by_date(json_data), "tab:blue",
         _("Observations per Date"), _("Observations")),
        (axes[1], observation_counts_by_date(json_data, abnormal_only=True), "tab:red",
         _("Abnormal Results per Date"), _("Abnormal Results")),
    ]
    for ax, counts, color, title, ylabel in plots:
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        if counts:
            dates = [date for date, count in counts]
            values = [count for date, count in counts]
            ax.vlines(dates, 0, values, color=color)
            ax.plot(dates, values, "o", color=color)
            ax.set_ylim(bottom=0)
        else:
            _no_data(ax, _("No data"))

    fig.autofmt_xdate()
    fig.tight_layout()
    return fig
