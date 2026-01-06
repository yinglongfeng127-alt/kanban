import pandas as pd

from update_market import last_nth, pct_change


def test_pct_change_computes_percentage():
    assert pct_change(110, 100) == 10
    assert pct_change(90, 100) == -10


def test_pct_change_handles_invalid_inputs():
    assert pct_change(None, 100) is None
    assert pct_change(100, None) is None
    assert pct_change(100, 0) is None


def test_last_nth_skips_nans_and_bounds():
    series = pd.Series([1.0, None, 3.0, 4.0])
    assert last_nth(series, 0) == 4.0
    assert last_nth(series, 1) == 3.0
    assert last_nth(series, 2) == 1.0
    assert last_nth(series, 3) is None
