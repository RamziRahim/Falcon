import numpy as np
import pandas as pd
import pytest

from scoring import conviction as cv
from tests.download_delivery import parse_full, parse_mto


# ----------------------------------------------------------------- volume profile
def test_profile_value_area_holds_70pct_and_contains_poc():
    rng = np.random.default_rng(0)
    mid = 100 + rng.normal(0, 3, 60)
    w = rng.uniform(1, 2, 60)
    p = cv.volume_profile(mid + 1, mid - 1, w)
    assert cv.share_between(p, p.val - 1e-9, p.vah) >= 0.70 - 1e-9
    assert p.val <= p.poc <= p.vah
    assert p.weight.sum() == pytest.approx(w.sum())


def test_profile_conserves_weight_and_spreads_evenly():
    p = cv.volume_profile([110, 110], [100, 100], [5.0, 5.0], bins=10)
    assert p.weight.sum() == pytest.approx(10.0)
    assert np.allclose(p.weight, 1.0)


def test_profile_point_session_goes_to_one_bin():
    p = cv.volume_profile([110, 105], [100, 105], [1.0, 7.0], bins=10)
    assert p.weight.argmax() == 5 and p.poc == pytest.approx(105.5)


def test_profile_degenerate_inputs():
    assert cv.volume_profile([100], [100], [1.0]) is None
    assert cv.volume_profile([np.nan], [np.nan], [1.0]) is None


def test_vp_point_breakout_above_value_with_clear_air():
    h = np.r_[np.full(59, 101.0), 112.0]
    l = np.r_[np.full(59, 99.0), 104.0]
    c = np.r_[np.full(59, 100.0), 111.0]
    pt, info = cv.vp_point(h, l, c, np.ones(60))
    assert pt == 1 and info["above_value"] and info["overhead_share"] < 0.10


def test_vp_point_zero_inside_value():
    h, l, c = np.full(60, 101.0), np.full(60, 99.0), np.full(60, 100.0)
    h[0], l[0] = 110.0, 90.0
    assert cv.vp_point(h, l, c, np.ones(60))[0] == 0


def test_vp_point_zero_when_heavy_supply_overhead():
    # value sits low, but a heavy shelf sits 3-8% above the close
    h = np.r_[np.full(30, 101.0), np.full(29, 108.0), 102.0]
    l = np.r_[np.full(30, 99.0), np.full(29, 105.0), 100.0]
    w = np.r_[np.full(30, 10.0), np.full(29, 3.0), 1.0]
    c = np.r_[np.full(59, 100.0), 101.9]
    pt, info = cv.vp_point(h, l, c, w)
    assert info["above_value"] and info["overhead_share"] > 0.10 and pt == 0


# ----------------------------------------------------------------- delivery points
def test_delivery_point_threshold():
    base = np.full(20, 40.0)
    assert cv.delivery_point(np.r_[base, 52.0])[0] == 1          # 1.3 x 40
    assert cv.delivery_point(np.r_[base, 51.9])[0] == 0


def test_delivery_point_needs_15_valid_days_and_today():
    d = np.r_[np.full(6, np.nan), np.full(14, 40.0), 90.0]
    assert cv.delivery_point(d) == (0, {"dlv_ok": False})
    assert cv.delivery_point(np.r_[np.full(20, 40.0), np.nan])[1]["dlv_ok"] is False


def test_accumulation_point():
    closes = np.array([100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100], float)
    up_heavy = np.where(np.diff(closes) > 0, 60.0, 30.0)
    assert cv.accumulation_point(closes, up_heavy, np.ones(10))[0] == 1
    assert cv.accumulation_point(closes, 90 - up_heavy, np.ones(10))[0] == 0
    sparse = up_heavy.copy()
    sparse[:4] = np.nan
    assert cv.accumulation_point(closes, sparse, np.ones(10))[1]["acc_ok"] is False


def test_multiplier_map():
    assert [cv.multiplier(s) for s in range(4)] == [0.75, 1.0, 1.5, 1.5]


# ----------------------------------------------------------------- panel scoring / lookahead
def _data(n=120, seed=1):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2020-01-01", periods=n)
    close = pd.DataFrame({"X": 100 + np.cumsum(rng.normal(0, 1, n))}, index=days)
    frame = lambda v: pd.DataFrame({"X": v}, index=days)
    return cv.ConvictionData(frame(close["X"] + 1), frame(close["X"] - 1), close,
                             frame(rng.uniform(1e7, 2e7, n)), frame(rng.uniform(20, 60, n)))


def test_no_lookahead_entry_day_and_later_data_ignored():
    data = _data()
    trades = pd.DataFrame({"entity_id": ["X"], "entry_date": [data.sessions[100]], "exit_date": [data.sessions[110]],
                           "cost_basis": [1.0], "pnl": [0.1], "exit_reason": ["TARGET"]})
    before = cv.score_trades(data, trades).iloc[0]
    for f in (data.high, data.low, data.close, data.turnover, data.deliv_pct):
        f.iloc[100:] = f.iloc[100:] * 7 + 3                    # wreck entry day and after
    after = cv.score_trades(data, trades).iloc[0]
    assert before["t0"] == data.sessions[99]
    assert before[["score", "vp", "dlv", "acc"]].tolist() == after[["score", "vp", "dlv", "acc"]].tolist()


def test_score_uses_t0_data():
    data = _data()
    trades = pd.DataFrame({"entity_id": ["X"], "entry_date": [data.sessions[100]], "exit_date": [data.sessions[110]],
                           "cost_basis": [1.0], "pnl": [0.1], "exit_reason": ["TARGET"]})
    data.deliv_pct.iloc[79:99] = 30.0
    data.deliv_pct.iloc[99] = 10.0
    assert cv.score_trades(data, trades).iloc[0]["dlv"] == 0
    data.deliv_pct.iloc[99] = 95.0
    assert cv.score_trades(data, trades).iloc[0]["dlv"] == 1


def test_open_at_end_dropped_and_unknown_entity_scores_zero():
    data = _data()
    trades = pd.DataFrame({"entity_id": ["X", "Y"], "entry_date": [data.sessions[100]] * 2,
                           "exit_date": [data.sessions[110]] * 2, "cost_basis": [1.0, 1.0],
                           "pnl": [0.1, 0.2], "exit_reason": ["OPEN_AT_END", "STOP"]})
    s = cv.score_trades(data, trades)
    assert len(s) == 1 and s.iloc[0]["score"] == 0 and s.iloc[0]["mult"] == 0.75


def test_delivery_wide_keeps_eq_only_and_maps_symbol_changes():
    days = pd.to_datetime(["2020-01-01", "2020-01-02"])
    prices = pd.DataFrame({"Date": days, "Symbol": ["OLD", "NEW"], "Series": ["EQ", "EQ"], "entity_id": ["E1", "E1"]})
    deliv = pd.DataFrame({"Date": list(days) * 2, "Symbol": ["OLD", "NEW", "OLD", "NEW"],
                          "Series": ["EQ", "EQ", "BE", "BE"], "DelivPct": [40.0, 50.0, 100.0, 100.0]})
    w = cv.delivery_wide(prices, deliv, pd.DatetimeIndex(days), ["E1"])
    assert w["E1"].tolist() == [40.0, 50.0]


# ----------------------------------------------------------------- judgement
def _scored(means, n=40, sd=0.02, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for score, m in zip((0, 1, 2), means):
        rows += [{"score": score, "net": x} for x in rng.normal(m, sd, n)]
    s = pd.DataFrame(rows)
    s["bucket"], s["mult"] = s["score"].map(cv.BUCKETS), s["score"].map(cv.MULTIPLIER)
    s["dlv_ok"] = s["vp_ok"] = True
    return s


def test_judge_passes_clear_monotone_signal():
    r = cv.judge_buckets(_scored([0.00, 0.01, 0.03]))
    assert r["passed"] and r["sized_mean_net_pct"] > r["mean_net_pct"]


def test_judge_fails_non_monotone_or_small_or_thin():
    assert not cv.judge_buckets(_scored([0.00, 0.04, 0.03]))["passed"]
    assert not cv.judge_buckets(_scored([0.00, 0.002, 0.005]))["passed"]
    assert not cv.judge_buckets(_scored([0.00, 0.01, 0.03], n=20))["passed"]


# ----------------------------------------------------------------- NSE file parsers
def test_parse_mto():
    text = ("Security Wise Delivery Position - Compulsory Rolling Settlement\n"
            "10,MTO,27112026,123456789,0000000\n"
            "Trade Date <27-NOV-2026>,Settlement Type <N>,Settlement No <2026227>\n"
            "Record Type,Sr No,Name of Security,Series,Quantity Traded,Deliverable Quantity,% of Deliverable Quantity\n"
            "20,1,TCS,EQ,1000,600,60.00\n20,2,ABC,BE,50,50,100.00\n")
    df = parse_mto(text, pd.Timestamp("2026-11-27").date())
    assert df[["Symbol", "Series"]].values.tolist() == [["TCS", "EQ"], ["ABC", "BE"]]
    assert df["DelivPct"].tolist() == [60.0, 100.0] and df["DelivQty"].iloc[0] == 600


def test_parse_full():
    text = ("SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, "
            "AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
            "TCS, EQ, 27-Nov-2026, 1,1,1,1,1,1,1, 1000, 1, 1, 600, 60.00\n"
            "XYZ, BL, 27-Nov-2026, 1,1,1,1,1,1,1, 10, 1, 1, -, -\n")
    df = parse_full(text, pd.Timestamp("2026-11-27").date())
    assert df["DelivPct"].iloc[0] == 60.0 and np.isnan(df["DelivPct"].iloc[1])
