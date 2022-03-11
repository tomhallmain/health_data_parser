import matplotlib.pyplot as plt
import numpy as np
import os



def set_stats(stats: dict, value):
    stats["list"].append(value)
    stats["count"] += 1
    stats["sum"] += value
    if stats["max"] == None:
        stats["max"] = value
        stats["min"] = value
    elif stats["max"] < value:
        stats["max"] = value
    elif stats["min"] > value:
        stats["min"] = value




class PulseStatsGraph:
    def __init__(self, pulse_stats):
        '''
        date_pulse_readings = {}
        for obs in pulse_stats["list"]:
            date = obs["time"].toordinal()
            readings_stats_by_date = {}
            if date in date_pulse_readings:
                readings_on_date = date_pulse_readings[date]["list"]
            else:
                readings_on_date = []
            readings_on_date.append(obs["value"])
            readings_stats_by_date["list"] = readings_on_date
            date_pulse_readings[date] = readings_stats_by_date
        '''

        # For each day in the series, split it into minute increments and
        # calculate the average pulse during this minute
        day_minute_readings = {}
        day_minute_motion_readings = {}
        instances_of_heart_rate_spike = {}
        self.minutes = []
        _max = pulse_stats["max"]
        _min = pulse_stats["min"]

        for i in range(60 * 24):
            self.minutes.append(i)
            day_minute_readings[i] = {"max": None, "min": None, "count": 0, "sum": 0, "list": []}
            day_minute_motion_readings[i] = {"max": None, "min": None, "count": 0, "sum": 0, "list": []}
            instances_of_heart_rate_spike[i] = 0

        save_minute = -1
        spike_minute = -1
        save_value = 0
        save_duration = 0
        has_potential_spike = False
        self.values_in_motion = []
        self.values_resting = []
        self.max_in_motion = None
        self.min_in_motion = None
        self.max_resting = None
        self.min_resting = None
        sum_in_motion = 0
        sum_resting = 0

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

            if has_potential_spike:
                save_duration += minute - save_minute
                if save_duration >= 5:
                    has_potential_spike = False
                elif save_duration < 5 and save_value - value >= 40:
                    instances_of_heart_rate_spike[save_minute] += 1
            else:
                if minute - save_minute < 5 and value - save_value >= 40:
                    has_potential_spike = True
                    spike_minute = minute
                    save_duration = minute - save_minute
            save_minute = minute
            save_value = value

        
        self.values_in_motion.sort()
        self.values_resting.sort()
        self.values_in_motion = np.array(self.values_in_motion)
        self.values_resting = np.array(self.values_resting)
        self.avg_in_motion = np.average(self.values_in_motion)
        self.avg_resting = np.average(self.values_resting)

        self.minutes = np.array(self.minutes)
        self.max = []
        self.min = []
        self.count = []
        self.stDevs = []
        self.avgs = []
        self.maxMotion = []
        self.minMotion = []
        self.countMotion = []
        self.stDevsMotion = []
        self.avgsMotion = []
        self.spikeCounts = []

        for minute in day_minute_readings.keys():
            minute_stats = day_minute_readings[minute]
            count = minute_stats["count"]
            self.count.append(count)
            if count == 0:
                self.max.append(numpy.nan)
                self.min.append(numpy.nan)
                self.avgs.append(numpy.nan)
                self.stDevs.append(numpy.nan)
            else:
                self.max.append(minute_stats["max"])
                self.min.append(minute_stats["min"])
                avg = minute_stats["sum"] / count
                self.avgs.append(avg)
                del minute_stats["sum"]
                sum_sq_diffs = 0
                for value in minute_stats["list"]:
                    sum_sq_diffs += (value - avg) ** 2
                self.stDevs.append((sum_sq_diffs / count) ** (1/2))

            minute_stats = day_minute_motion_readings[minute]
            count = minute_stats["count"]
            self.countMotion.append(count)
            if count == 0:
                self.maxMotion.append(numpy.nan)
                self.minMotion.append(numpy.nan)
                self.avgsMotion.append(numpy.nan)
                self.stDevsMotion.append(numpy.nan)
            else:
                self.maxMotion.append(minute_stats["max"])
                self.minMotion.append(minute_stats["min"])
                avg = minute_stats["sum"] / count
                self.avgsMotion.append(avg)
                del minute_stats["sum"]
                sum_sq_diffs = 0
                for value in minute_stats["list"]:
                    sum_sq_diffs += (value - avg) ** 2
                self.stDevsMotion.append((sum_sq_diffs / count) ** (1/2))

            self.spikeCounts.append(instances_of_heart_rate_spike[minute])


    def save_graph_images(self, base_dir: str):
        self.save_loc = os.path.join(base_dir, "avg_heart_rate_obs.png")
        fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, gridspec_kw={'height_ratios': [4, 1, 1]})
        ax1.set_title("Average heart rate over 24 hours (+/– one standard deviation)")
        ax1.set_ylabel("BPM")
        ax1.set_xlabel("Time (minutes)")
        ax2.set_ylabel("% of readings in motion")
        ax2.set_xlabel("Time (minutes)")
        ax3.set_ylabel("Counts of pulse spike")
        ax3.set_xlabel("Time (minutes)")
        x = self.minutes
        y_est = np.array(self.avgs)
        y_err = np.array(self.stDevs)
        ax1.plot(x, np.array(self.avgs), "-")
        ax1.fill_between(x, y_est - y_err, y_est + y_err, alpha=0.4)
        #ax1.fill_between(x, y_est - y_err, np.array(self.min), color="red", alpha=0.1)
        #ax1.fill_between(x, y_est + y_err, np.array(self.max), color="red", alpha=0.1)
        smoother = 20
        y_est = np.pad(np.array(self.avgsMotion), (smoother//2, smoother-smoother//2), mode="edge")
        y_est = np.cumsum(y_est[smoother:] - y_est[:-smoother]) / smoother
        y_err = np.pad(np.array(self.stDevsMotion), (smoother//2, smoother-smoother//2), mode="edge")
        y_err = np.cumsum(y_err[smoother:] - y_err[:-smoother]) / smoother
        ax2.plot(x, y_est, "-", color="black")
        ax3.plot(x, np.array(self.spikeCounts), color="black")
        ax3.fill_between(x, 0, np.array(self.spikeCounts), color="black")
        fig.set_size_inches(10, 12)
        #plt.show()
        fig.savefig(self.save_loc, pad_inches=0.02, bbox_inches='tight')




