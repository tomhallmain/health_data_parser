from datetime import date, datetime

import numpy as np
import pytest

from health_data_parser.reporting.charts.vitals import VitalsStatsGraph, smooth


def nan_list(values):
    """For comparing arrays containing NaN: NaN != NaN, so map it to None."""
    return [None if np.isnan(v) else v for v in values]


class TestSmooth:
    def test_factor_one_is_identity(self):
        assert smooth([1.0, 2.0, 3.0, 4.0, 5.0], 1).tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_window_is_centered_for_odd_factor(self):
        assert smooth([0.0, 0.0, 3.0, 0.0, 0.0], 3).tolist() == [0.0, 1.0, 1.0, 1.0, 0.0]

    def test_series_edges_are_extended(self):
        # Window for the first point is [1, 1, 4] with the left edge repeated
        assert smooth([1.0, 4.0, 7.0], 3).tolist() == [2.0, 4.0, 6.0]

    def test_constant_series_is_unchanged(self):
        assert smooth([5.0] * 6, 3).tolist() == [5.0] * 6

    @pytest.mark.parametrize("factor", [1, 2, 3, 10, 20])
    def test_length_is_preserved(self, factor):
        assert len(smooth(list(range(30)), factor)) == 30

    def test_interior_gaps_are_interpolated(self):
        assert smooth([4.0, np.nan, 8.0], 1).tolist() == [4.0, 6.0, 8.0]
        assert smooth([2.0, np.nan, np.nan, 8.0], 1).tolist() == [2.0, 4.0, 6.0, 8.0]

    def test_none_counts_as_a_gap(self):
        assert smooth([4.0, None, 8.0], 1).tolist() == [4.0, 6.0, 8.0]

    def test_leading_and_trailing_gaps_stay_empty(self):
        # e.g. no heart rate reading in the first minutes after midnight
        assert nan_list(smooth([np.nan, np.nan, 5.0, 5.0, np.nan], 2)) == [None, None, 5.0, 5.0, None]

    def test_gaps_can_be_zero_padded(self):
        assert smooth([np.nan, 5.0, 5.0, np.nan], 2, pad_with_zeros=True).tolist() == [0.0, 5.0, 5.0, 0.0]

    def test_all_gaps(self):
        assert nan_list(smooth([np.nan, np.nan], 3)) == [None, None]
        assert smooth([None, None], 3, pad_with_zeros=True).tolist() == [0.0, 0.0]

    def test_gap_is_filled_before_averaging(self):
        assert smooth([0.0, np.nan, 6.0], 3).tolist() == [1.0, 3.0, 5.0]


DAY_1, DAY_2, DAY_3 = 1, 2, 3


def reading(day, hour, minute, value, motion=None):
    obs = {"time": datetime(2023, 1, day, hour, minute), "value": value}
    if motion is not None:
        obs["motion"] = motion
    return obs


def ordinal(day):
    return date(2023, 1, day).toordinal()


@pytest.fixture
def graph():
    """Readings over three days with none on day 2.

    Pulse, day 1: 60 at 08:00, 110 at 08:02 (a spike), 70 at 12:00 in motion.
    Pulse, day 3: 80 at 08:00.
    """
    pulse = {"list": [reading(DAY_1, 8, 0, 60, 0), reading(DAY_1, 8, 2, 110, 0),
                      reading(DAY_1, 12, 0, 70, 1), reading(DAY_3, 8, 0, 80, 0)]}
    hrv = {"list": [reading(DAY_1, 9, 0, 50)]}
    steps = {"list": [reading(DAY_1, 10, 0, 100), reading(DAY_1, 11, 0, 200), reading(DAY_3, 10, 0, 50)]}
    stand = {"list": [reading(DAY_1, 10, 0, 2), reading(DAY_3, 10, 0, 4)]}
    return VitalsStatsGraph(ordinal(DAY_1), pulse, hrv, steps, stand)


class TestVitalsStatsGraphDailyStats:
    def test_date_range(self, graph):
        assert graph.min_pulse_ordinal == ordinal(DAY_1)
        assert graph.max_ordinal == ordinal(DAY_3)
        assert graph.pulse_dates == [ordinal(DAY_1), ordinal(DAY_3)]

    def test_pulse_by_day(self, graph):
        stats = graph.pulse_date_stats
        assert stats["count"] == [3, 0, 1]
        assert nan_list(stats["avgs"]) == [80.0, None, 80.0]
        assert nan_list(stats["max"]) == [110, None, 80]
        assert nan_list(stats["min"]) == [60, None, 80]
        assert stats["stdevs"][0] == pytest.approx((1400 / 3) ** 0.5)
        assert stats["stdevs"][2] == 0.0

    def test_hrv_by_day(self, graph):
        assert graph.hrv_date_stats["count"] == [1, 0, 0]
        assert nan_list(graph.hrv_date_stats["avgs"]) == [50.0, None, None]

    def test_steps_and_stand_keep_daily_sums(self, graph):
        assert graph.step_date_stats["sums"] == [300, 0, 50]
        assert graph.stand_date_stats["sums"] == [2, 0, 4]

    def test_pulse_stand_ratio(self, graph):
        # Average pulse / stand minutes, 0 where either is missing
        assert graph.pulse_stand_ratios == [40.0, 0, 20.0]

    def test_readings_before_min_ordinal_are_ignored(self):
        pulse = {"list": [reading(DAY_1, 8, 0, 60, 0), reading(DAY_2, 8, 0, 70, 0)]}
        empty = {"list": []}
        graph = VitalsStatsGraph(ordinal(DAY_2), pulse, empty, empty, empty)
        assert graph.pulse_dates == [ordinal(DAY_2)]
        assert graph.pulse_date_stats["count"] == [1]

    def test_no_readings_raises(self):
        empty = {"list": []}
        with pytest.raises(AssertionError, match="Error collecting dates"):
            VitalsStatsGraph(0, {"list": []}, empty, empty, empty)


class TestVitalsStatsGraphMinuteStats:
    def test_readings_are_grouped_by_minute_of_day(self, graph):
        assert len(graph.minutes) == 24 * 60
        assert graph.minute_count[8 * 60] == 2  # 08:00 on days 1 and 3
        assert graph.minute_avgs[8 * 60] == 70.0
        assert graph.minute_avgs[8 * 60 + 2] == 110.0
        assert np.isnan(graph.minute_avgs[0])

    def test_motion_by_minute(self, graph):
        assert graph.motion_avgs[12 * 60] == 1.0
        assert graph.motion_avgs[8 * 60] == 0.0

    def test_in_motion_and_resting(self, graph):
        # In motion: motion context set, or pulse above 105
        assert graph.values_in_motion.tolist() == [70, 110]
        assert graph.values_resting.tolist() == [60, 80]
        assert graph.avg_in_motion == 90.0
        assert graph.avg_resting == 70.0

    def test_spike_is_counted_at_its_start_minute(self, graph):
        assert graph.spikeCounts[8 * 60] == 1
        assert sum(graph.spikeCounts) == 1

    @pytest.mark.xfail(reason="Known bug: spikes compare minute of day, so readings a day apart "
                              "at nearby times of day count as a spike")
    def test_readings_on_different_days_are_not_a_spike(self):
        pulse = {"list": [reading(DAY_1, 8, 0, 60, 0), reading(DAY_2, 8, 1, 110, 0)]}
        empty = {"list": []}
        graph = VitalsStatsGraph(ordinal(DAY_1), pulse, empty, empty, empty)
        assert sum(graph.spikeCounts) == 0


def test_save_graph_images(graph, tmp_path):
    # Minute 0 has no reading, so the per-minute motion series starts with a gap
    graph.save_graph_images(str(tmp_path))
    assert graph.to_print
    assert (tmp_path / "avg_heart_rates_by_minute.png").exists()
    assert (tmp_path / "avgs_by_day_trends.png").exists()
