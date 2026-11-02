import numpy as np

from tests.refit_on_honest_labels import reading_a_cutoff


def test_reading_a_picks_lowest_quintile_with_no_dip_above_base():
    p = np.linspace(0.05, 0.95, 50)
    y = (p > 0.55).astype(int)                       # wins concentrated in the top two quintiles
    cutoff, table, base = reading_a_cutoff(y, p)
    assert base == y.mean()
    assert cutoff == table["p_min"].iloc[3]


def test_reading_a_returns_none_when_nothing_beats_base():
    p = np.linspace(0.05, 0.95, 50)
    y = (p < 0.25).astype(int)                       # inverted: low p wins
    cutoff, _, _ = reading_a_cutoff(y, p)
    assert cutoff is None
