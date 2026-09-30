from datetime import datetime, timedelta
from matplotlib.figure import Figure
import numpy as np
import os

from health_data_parser.utils.translations import _

MINUTES_PER_DAY = 24 * 60


def _summary(values):
    """(count, max, min, mean, population stdev) of values; NaN stats for none."""
    count = len(values)
    if count == 0:
        return 0, np.nan, np.nan, np.nan, np.nan
    mean = sum(values) / count
    stdev = (sum((value - mean) ** 2 for value in values) / count) ** (1 / 2)
    return count, max(values), min(values), mean, stdev


def smooth(data, smoothing_factor: int, pad_with_zeros=False):
    """Moving average over a window of smoothing_factor points around each point.

    Gaps (None/NaN) before the first and after the last value stay gaps in the
    output (zeros with pad_with_zeros); gaps between values are filled by linear
    interpolation before averaging. The output has the same length as data.
    """
    values = np.array([np.nan if v is None else v for v in data], dtype=float)
    pad_value = 0.0 if pad_with_zeros else np.nan
    present = np.flatnonzero(~np.isnan(values))
    if len(present) == 0:
        return np.full(len(values), pad_value)
    first, last = present[0], present[-1]

    values = values[first:last + 1]
    gaps = np.isnan(values)
    if gaps.any():
        indexes = np.arange(len(values))
        values[gaps] = np.interp(indexes[gaps], indexes[~gaps], values[~gaps])

    # The window for point i covers values[i - left : i + right + 1], with the
    # series edges extended to fill it
    left = smoothing_factor // 2
    right = smoothing_factor - 1 - left
    padded = np.pad(values, (left, right), mode="edge")
    cumsum = np.concatenate([[0.0], np.cumsum(padded)])
    smoothed = (cumsum[smoothing_factor:] - cumsum[:-smoothing_factor]) / smoothing_factor

    return np.concatenate([np.full(first, pad_value), smoothed,
                           np.full(len(data) - 1 - last, pad_value)])


class VitalsStatsGraph:
    """Daily and time-of-day statistics from wearable heart rate, HRV, step and
    stand readings, and the charts drawn from them.

    Each series argument is a VitalSeries. Daily stats ignore readings dated
    before `min_xml_ordinal` (a date ordinal; None for no limit) and cover
    each date from the first heart rate reading to the last reading of any
    series.
    """

    def __init__(self, min_xml_ordinal, pulse, hrv, steps, stand):
        self.to_print = False
        self.min_xml_ordinal = min_xml_ordinal
        self.collect_daily_stats(pulse, hrv, steps, stand)
        self.calculate_pulse_stand_ratio()
        self.collect_minute_pulse_stats(pulse)

    def collect_daily_stats(self, pulse, hrv, steps, stand):
        pulse_by_date, hrv_by_date, step_by_date, stand_by_date = by_date = [
            self._values_by_date(series) for series in (pulse, hrv, steps, stand)]
        self.pulse_dates = list(pulse_by_date)
        self.hrv_dates = list(hrv_by_date)
        self.step_dates = list(step_by_date)
        self.stand_dates = list(stand_by_date)

        all_dates = [date for dates in by_date for date in dates]
        if not all_dates:
            raise AssertionError("Error collecting dates from pulse, HRV,"
                                 + " step, or stand observations data")
        self.max_ordinal = max(all_dates)
        # With no heart rate dates the date range is empty
        self.min_pulse_ordinal = min(pulse_by_date) if pulse_by_date else self.max_ordinal + 1

        self.pulse_date_stats = self._daily_stats(pulse_by_date)
        self.hrv_date_stats = self._daily_stats(hrv_by_date)
        self.step_date_stats = self._daily_stats(step_by_date)
        self.stand_date_stats = self._daily_stats(stand_by_date)

    def _values_by_date(self, series):
        """Date ordinal -> reading values, dates in the order first seen."""
        by_date = {}
        for reading in series.readings:
            date = reading.time.toordinal()
            if self.min_xml_ordinal is not None and date < self.min_xml_ordinal:
                continue
            by_date.setdefault(date, []).append(reading.value)
        return by_date

    def _daily_stats(self, values_by_date):
        """Per-date lists over the graph's date range, NaN (0 for sums) on dates
        without readings."""
        stats = {"max": [], "min": [], "count": [], "stdevs": [], "avgs": [], "sums": []}
        for date in range(self.min_pulse_ordinal, self.max_ordinal + 1):
            values = values_by_date.get(date, [])
            count, maximum, minimum, mean, stdev = _summary(values)
            stats["count"].append(count)
            stats["max"].append(maximum)
            stats["min"].append(minimum)
            stats["avgs"].append(mean)
            stats["stdevs"].append(stdev)
            stats["sums"].append(sum(values))
        return stats

    def calculate_pulse_stand_ratio(self):
        self.pulse_stand_ratios = []
        for date_index in range(0, self.max_ordinal + 1 - self.min_pulse_ordinal):
            if (self.pulse_date_stats["count"][date_index] > 0
                    and self.stand_date_stats["count"][date_index] > 0):
                self.pulse_stand_ratios.append(
                    self.pulse_date_stats["avgs"][date_index]
                    / self.stand_date_stats["sums"][date_index])
            else:
                self.pulse_stand_ratios.append(0)

    # For each day in the series, split it into minute increments and
    # calculate the average pulse during this minute
    def collect_minute_pulse_stats(self, pulse):
        minute_values = [[] for _ in range(MINUTES_PER_DAY)]
        minute_motions = [[] for _ in range(MINUTES_PER_DAY)]
        spike_counts = [0] * MINUTES_PER_DAY
        values_in_motion = []
        values_resting = []

        previous = None
        for reading in pulse.readings:
            minute = reading.time.hour * 60 + reading.time.minute
            motion = reading.motion or 0
            minute_values[minute].append(reading.value)
            minute_motions[minute].append(motion)

            if motion > 0 or reading.value > 105:
                values_in_motion.append(reading.value)
            else:
                values_resting.append(reading.value)

            # A rise of more than 40 BPM within 5 minutes, counted at the minute
            # of day it started from
            if (previous is not None
                    and timedelta(0) <= reading.time - previous.time < timedelta(minutes=5)
                    and reading.value - previous.value > 40):
                spike_counts[previous.time.hour * 60 + previous.time.minute] += 1
            previous = reading

        self.values_in_motion = np.array(sorted(values_in_motion))
        self.values_resting = np.array(sorted(values_resting))
        # NaN when there are no readings of that kind
        self.avg_in_motion = self.values_in_motion.mean() if len(self.values_in_motion) else np.nan
        self.avg_resting = self.values_resting.mean() if len(self.values_resting) else np.nan
        self.minutes = np.arange(MINUTES_PER_DAY)
        self.minute_max = []
        self.minute_min = []
        self.minute_count = []
        self.minute_stdevs = []
        self.minute_avgs = []
        self.motion_max = []
        self.motion_min = []
        self.motion_count = []
        self.motion_stdevs = []
        self.motion_avgs = []
        self.spikeCounts = spike_counts

        for minute in range(MINUTES_PER_DAY):
            count, maximum, minimum, mean, stdev = _summary(minute_values[minute])
            self.minute_count.append(count)
            self.minute_max.append(maximum)
            self.minute_min.append(minimum)
            self.minute_avgs.append(mean)
            self.minute_stdevs.append(stdev)
            count, maximum, minimum, mean, stdev = _summary(minute_motions[minute])
            self.motion_count.append(count)
            self.motion_max.append(maximum)
            self.motion_min.append(minimum)
            self.motion_avgs.append(mean)
            self.motion_stdevs.append(stdev)

    def save_graph_images(self, base_dir: str):
        self.save_loc_minutes_data = os.path.join(
            base_dir, "avg_heart_rates_by_minute.png")
        fig = Figure()
        ax1, ax2, ax3 = fig.subplots(nrows=3, ncols=1, gridspec_kw={'height_ratios': [4, 1, 1]})
        ax1.set_title(
            _("Average heart rates over 24 hours (+/– one standard deviation)"))
        ax1.set_ylabel(_("BPM"))
        ax1.set_xlabel(_("Time (minutes)"))
        ax2.set_ylabel(_("Average motion context"))
        ax2.set_xlabel(_("Time (minutes)"))
        ax3.set_ylabel(_("Counts of pulse spike"))
        ax3.set_xlabel(_("Time (minutes)"))
        x = self.minutes
        y_est = np.array(self.minute_avgs)
        y_err = np.array(self.minute_stdevs)
        ax1.plot(x, y_est, "-")
        ax1.fill_between(x, y_est - y_err, y_est + y_err, alpha=0.4)
        # ax1.fill_between(x, y_est - y_err, np.array(self.minute_min), color="red", alpha=0.1)
        # ax1.fill_between(x, y_est + y_err, np.array(self.minute_max), color="red", alpha=0.1)
        y_est = smooth(np.array(self.motion_avgs), 20)
        # y_err = smooth(np.array(self.motion_stdevs), 20)
        ax2.plot(x, y_est, "-", color="black")
        ax3.plot(x, np.array(self.spikeCounts), color="black")
        ax3.fill_between(x, 0, np.array(self.spikeCounts), color="black")
        fig.set_size_inches(10, 12)
        fig.savefig(self.save_loc_minutes_data,
                    pad_inches=0.02, bbox_inches='tight')
        fig.clear(True)

        self.save_loc_dates_data = os.path.join(
            base_dir, "avgs_by_day_trends.png")
        fig = Figure()
        ax1, ax2, ax3, ax4 = fig.subplots(nrows=4, ncols=1, gridspec_kw={'height_ratios': [5, 1, 1, 1]})
        ax1.set_title(_("Average heart rates, steps and stand minutes by day"))
        ax1.set_ylabel(_("BPM"))
        ax2.set_ylabel(_("Apple steps"))
        ax3.set_ylabel(_("Apple stand minutes"))
        ax4.set_ylabel(_("BPM / stand min"))
        ax4.set_xlabel(_("Days"))
        x = np.array(list(map(lambda o: datetime.fromordinal(o),
                              list(range(self.min_pulse_ordinal,
                                         self.max_ordinal + 1)))))
        y_est = smooth(self.pulse_date_stats["avgs"], 10)
        y_err = smooth(self.pulse_date_stats["stdevs"], 10)
        y_min = smooth(self.pulse_date_stats["min"], 10)
        y_max = smooth(self.pulse_date_stats["max"], 10)
        ax1.plot(x, y_est, "-")
        ax1.fill_between(x, y_est - y_err, y_est + y_err, alpha=0.4)
        ax1.fill_between(x, y_est + y_err, y_max, color="red", alpha=0.1)
        ax1.fill_between(x, y_est - y_err, y_min, color="orange", alpha=0.1)
        y_est = smooth(self.step_date_stats["sums"], 10)
        ax2.plot(x, y_est, "-", color="black")
        ax2.fill_between(x, np.zeros(len(y_est)), y_est, color="black")
        y_est = smooth(self.stand_date_stats["sums"], 10)
        ax3.plot(x, y_est, "-", color="black")
        ax3.fill_between(x, np.zeros(len(y_est)), y_est, color="black")
        y_est = smooth(self.pulse_stand_ratios, 10)
        ax4.plot(x, y_est, "-", color="black")
        for label in ax4.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment("right")
        fig.set_size_inches(10, 12)
        fig.savefig(self.save_loc_dates_data,
                    pad_inches=0.02, bbox_inches='tight')

        self.to_print = True
