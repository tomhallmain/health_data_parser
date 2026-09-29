import numpy as np
import pytest

from reporting.graph import smooth


class TestSmooth:
    def test_constant_series_is_unchanged(self):
        assert smooth([5.0] * 6, 3).tolist() == [5.0] * 6

    @pytest.mark.parametrize("factor", [2, 10, 20])
    def test_length_is_preserved(self, factor):
        assert len(smooth(list(range(30)), factor)) == 30

    def test_interior_gaps_are_filled(self):
        result = smooth([4.0, np.nan, np.nan, 8.0, 8.0, 8.0], 2)
        assert not np.isnan(result).any()

    def test_trailing_gaps_stay_empty(self):
        result = smooth([5.0, 5.0, 5.0, np.nan, np.nan], 2)
        assert result[:3].tolist() == [5.0, 5.0, 5.0]
        assert np.isnan(result[3:]).all()

    def test_trailing_gaps_can_be_zero_padded(self):
        result = smooth([5.0, 5.0, 5.0, np.nan], 2, pad_with_zeros=True)
        assert result.tolist() == [5.0, 5.0, 5.0, 0.0]

    @pytest.mark.xfail(raises=UnboundLocalError,
                       reason="Known bug: the leading-gap branch increments end_nan_counter "
                              "before it exists (and never advances start_nan_counter)")
    def test_leading_gaps_stay_empty(self):
        # e.g. no heart rate reading in the first minutes after midnight
        result = smooth([np.nan, 5.0, 5.0, 5.0], 2)
        assert np.isnan(result[0])
        assert result[1:].tolist() == [5.0, 5.0, 5.0]
