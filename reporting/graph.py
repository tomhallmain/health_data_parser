from copy import deepcopy
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import os

from data.units import base_stats


def set_stats(stats: dict, value):
    stats["list"].append(value)
    stats["count"] += 1
    stats["sum"] += value
    if stats["max"] is None:
        stats["max"] = value
        stats["min"] = value
    elif stats["max"] < value:
        stats["max"] = value
    elif stats["min"] > value:
        stats["min"] = value


def smooth(data, smoothing_factor: int, pad_with_zeros=False):
    start_padding = []
    end_padding = []
    pad_value = 0 if pad_with_zeros else np.nan

    if data[0] is None or np.isnan(data[0]):
        end_nan_counter = 0
        data_len = len(data)
        while end_nan_counter < data_len:
            end_nan_counter += 1
            if data[end_nan_counter] is None or np.isnan(data[end_nan_counter]):
                start_padding.append(pad_value)
            else:
                start_padding.append(pad_value)
                break
        data = data[end_nan_counter:]

    if data[-1] is None or np.isnan(data[-1]):
        end_nan_counter = -1
        data_len = len(data)
        while end_nan_counter * -1 < data_len:
            end_nan_counter -= 1
            if data[end_nan_counter] is None or np.isnan(data[end_nan_counter]):
                end_padding.append(pad_value)
            else:
                end_padding.append(pad_value)
                break
        data = data[:end_nan_counter]

    data = np.array(data)

    if None in data or np.isnan(np.sum(data)):
        i = 0
        nans = []
        save_value = None
        is_nans = np.isnan(data)

        while i < len(data):
            value = data[i]
            if value is None or is_nans[i]:
                nans.append(i)
            elif len(nans) > 0:
                step = (value - save_value) / len(nans)
                for j in range(len(nans)):
                    nan_index = nans[j]
                    estimated_value = save_value + step * (j+1)
                    data[nan_index] = estimated_value
                nans = []
                save_value = value
            else:
                save_value = value
            i += 1

    data = np.pad(data, (smoothing_factor//2, smoothing_factor
                  - smoothing_factor//2), mode="edge")
    cumsum = np.cumsum(data)
    smoothed = (cumsum[smoothing_factor:]
                - cumsum[:-smoothing_factor]) / smoothing_factor
    return np.append(np.append(start_padding, smoothed), end_padding)


class VitalsStatsGraph:
    def __init__(self, min_xml_ordinal, pulse_stats, hrv_stats, step_stats, stand_stats):
        self.to_print = False
        self.min_xml_ordinal = min_xml_ordinal
        self.collect_daily_stats(
            pulse_stats, hrv_stats, step_stats, stand_stats)
        self.calculate_pulse_stand_ratio()
        self.collect_minute_pulse_stats(pulse_stats, hrv_stats)

    # For each date in the series, calculate statistics about readings
    def collect_daily_stats(self, pulse_stats, hrv_stats, step_stats, stand_stats):
        self.min_ordinal = 99999999
        self.max_ordinal = 0
        date_pulse_readings = {}
        date_pulse_hrv_readings = {}
        date_step_readings = {}
        date_stand_readings = {}
        self.pulse_dates = []
        self.hrv_dates = []
        self.step_dates = []
        self.stand_dates = []
        self.pulse_date_stats = {"max": [], "min": [], "count": [],
                                 "stdevs": [], "avgs": [], "sums": []}
        self.hrv_date_stats = deepcopy(self.pulse_date_stats)
        self.step_date_stats = deepcopy(self.pulse_date_stats)
        self.stand_date_stats = deepcopy(self.pulse_date_stats)

        self.set_daily_stats(
            pulse_stats, date_pulse_readings, self.pulse_dates)
        self.min_pulse_ordinal = self.min_ordinal
        self.set_daily_stats(
            hrv_stats, date_pulse_hrv_readings, self.hrv_dates)
        self.set_daily_stats(
            step_stats, date_step_readings, self.step_dates)
        self.set_daily_stats(
            stand_stats, date_stand_readings, self.stand_dates)

        if self.max_ordinal == 0:
            raise AssertionError("Error collecting dates from pulse, HRV,"
                                 + " step, or stand observations data")

        for date in range(self.min_pulse_ordinal, self.max_ordinal + 1):
            self.set_final_date_stats(
                date, date_pulse_readings, self.pulse_date_stats)
            self.set_final_date_stats(
                date, date_pulse_hrv_readings, self.hrv_date_stats)
            self.set_final_date_stats(
                date, date_step_readings, self.step_date_stats, True)
            self.set_final_date_stats(
                date, date_stand_readings, self.stand_date_stats, True)

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
    def collect_minute_pulse_stats(self, pulse_stats, hrv_stats):
        day_minute_readings = {}
        day_minute_motion_readings = {}
        instances_of_heart_rate_spike = {}
        self.minutes = []

        for i in range(60 * 24):
            self.minutes.append(i)
            day_minute_readings[i] = deepcopy(base_stats)
            day_minute_motion_readings[i] = deepcopy(base_stats)
            instances_of_heart_rate_spike[i] = 0

        save_minute = -1
        save_value = 0
        self.values_in_motion = []
        self.values_resting = []
        self.max_in_motion = None
        self.min_in_motion = None
        self.max_resting = None
        self.min_resting = None

        for obs in pulse_stats["list"]:
            minute = obs["time"].hour * 60 + obs["time"].minute
            value = obs["value"]
            motion = obs["motion"]
            set_stats(day_minute_readings[minute], value)
            set_stats(day_minute_motion_readings[minute], motion)

            if motion > 0 or value > 105:
                self.values_in_motion.append(value)
            else:
                self.values_resting.append(value)

            if (minute - save_minute < 5
                    and value - save_value > 40
                    and save_minute > -1):
                instances_of_heart_rate_spike[save_minute] += 1

            save_minute = minute
            save_value = value

        self.values_in_motion.sort()
        self.values_resting.sort()
        self.values_in_motion = np.array(self.values_in_motion)
        self.values_resting = np.array(self.values_resting)
        self.avg_in_motion = np.average(self.values_in_motion)
        self.avg_resting = np.average(self.values_resting)
        self.minutes = np.array(self.minutes)
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
        self.spikeCounts = []

        for minute in sorted(day_minute_readings.keys()):
            self.set_final_minute_stats(minute, day_minute_readings,
                                        self.minute_avgs, self.minute_stdevs,
                                        self.minute_count, self.minute_max,
                                        self.minute_min)
            self.set_final_minute_stats(minute, day_minute_motion_readings,
                                        self.motion_avgs, self.motion_stdevs,
                                        self.motion_count, self.motion_max,
                                        self.motion_min)
            # self.set_final_minute_stats(minute, day_minute_hrv_readings,
            #                             self.hrv_avgs, self.hrv_stdevs)
            self.spikeCounts.append(instances_of_heart_rate_spike[minute])

    def set_daily_stats(self, vital_stats, date_vital_stats, dates_list):
        for obs in vital_stats["list"]:
            date = obs["time"].toordinal()
            if date < self.min_xml_ordinal:
                continue
            elif date not in dates_list:
                dates_list.append(date)
            if self.min_ordinal > date:
                self.min_ordinal = date
            if self.max_ordinal < date:
                self.max_ordinal = date
            if date in date_vital_stats:
                date_stats = date_vital_stats[date]
            else:
                date_stats = deepcopy(base_stats)
            set_stats(date_stats, obs["value"])
            date_vital_stats[date] = date_stats

    def set_final_date_stats(self, date, data, final_stats, keep_sums=False):
        count = data[date]["count"] if (date in data) else 0
        final_stats["count"].append(count)
        if count == 0:
            final_stats["max"].append(np.nan)
            final_stats["min"].append(np.nan)
            final_stats["avgs"].append(np.nan)
            final_stats["stdevs"].append(np.nan)
            if keep_sums:
                final_stats["sums"].append(0)
        else:
            date_stats = data[date]
            final_stats["max"].append(date_stats["max"])
            final_stats["min"].append(date_stats["min"])
            avg = date_stats["sum"] / count
            final_stats["avgs"].append(avg)
            if keep_sums:
                final_stats["sums"].append(date_stats["sum"])
            else:
                del date_stats["sum"]
                sum_sq_diffs = 0
                for value in date_stats["list"]:
                    sum_sq_diffs += (value - avg) ** 2
                final_stats["stdevs"].append(
                    (sum_sq_diffs / count) ** (1/2))
            del data[date]

    def set_final_minute_stats(self, minute, minute_readings, avgs, stdevs,
                               counts=None, maxs=None, mins=None):
        minute_stats = minute_readings[minute]
        count = minute_stats["count"]
        if counts is not None:
            counts.append(count)
        if count == 0:
            if maxs is not None:
                maxs.append(np.nan)
            if mins is not None:
                mins.append(np.nan)
            avgs.append(np.nan)
            stdevs.append(np.nan)
        else:
            if maxs is not None:
                maxs.append(minute_stats["max"])
            if mins is not None:
                mins.append(minute_stats["min"])
            avg = minute_stats["sum"] / count
            avgs.append(avg)
            del minute_stats["sum"]
            sum_sq_diffs = 0
            for value in minute_stats["list"]:
                sum_sq_diffs += (value - avg) ** 2
            stdevs.append((sum_sq_diffs / count) ** (1/2))

    def save_graph_images(self, base_dir: str):
        self.save_loc_minutes_data = os.path.join(
            base_dir, "avg_heart_rates_by_minute.png")
        fig, (ax1, ax2, ax3) = plt.subplots(
            nrows=3, ncols=1, gridspec_kw={'height_ratios': [4, 1, 1]})
        ax1.set_title(
            "Average heart rates over 24 hours (+/– one standard deviation)")
        ax1.set_ylabel("BPM")
        ax1.set_xlabel("Time (minutes)")
        ax2.set_ylabel("Heart Rate Variability")
        ax2.set_xlabel("Time (minutes)")
        ax3.set_ylabel("Counts of pulse spike")
        ax3.set_xlabel("Time (minutes)")
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
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(
            nrows=4, ncols=1, gridspec_kw={'height_ratios': [5, 1, 1, 1]})
        ax1.set_title("Average heart rates, steps and stand minutes by day")
        ax1.set_ylabel("BPM")
        ax2.set_ylabel("Apple steps")
        ax3.set_ylabel("Apple stand minutes")
        ax4.set_ylabel("BPM / stand min")
        ax4.set_xlabel("Days")
        plt.xticks(rotation=30, ha='right')
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
        fig.set_size_inches(10, 12)
        fig.savefig(self.save_loc_dates_data,
                    pad_inches=0.02, bbox_inches='tight')

        self.to_print = True
