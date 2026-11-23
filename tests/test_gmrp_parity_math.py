"""Offline tests for put_call_parity: black_scholes, parity_engine, bayesian_threshold."""
import math
import sys
from datetime import date

import pytest

import gmrp_helpers as H

if H.ROOT not in sys.path:
    sys.path.insert(0, H.ROOT)

from put_call_parity import bayesian_threshold as bt  # noqa: E402
from put_call_parity import black_scholes as bs  # noqa: E402
from put_call_parity import config as cfgmod  # noqa: E402
from put_call_parity import parity_engine as pe  # noqa: E402


# ── black_scholes ────────────────────────────────────────────────────────────

S, K, T, R, SIG = 100.0, 100.0, 1.0, 0.05, 0.2


def test_reference_prices():
    assert bs.call_price(S, K, T, R, SIG) == pytest.approx(10.4506, abs=1e-3)
    assert bs.put_price(S, K, T, R, SIG) == pytest.approx(5.5735, abs=1e-3)


@pytest.mark.parametrize("k", [80.0, 100.0, 125.0])
@pytest.mark.parametrize("t", [0.05, 0.5, 2.0])
def test_put_call_parity_holds(k, t):
    c, p = bs.call_price(S, k, t, R, SIG), bs.put_price(S, k, t, R, SIG)
    assert c - p == pytest.approx(S - k * math.exp(-R * t), abs=1e-9)


def test_expiry_is_intrinsic_value():
    assert bs.call_price(110, 100, 0, R, SIG) == 10
    assert bs.call_price(90, 100, 0, R, SIG) == 0
    assert bs.put_price(90, 100, 0, R, SIG) == 10
    assert bs.put_price(110, 100, -1, R, SIG) == 0


def test_price_option_dispatch_is_case_insensitive():
    assert bs.price_option(S, K, T, R, SIG, "ce") == bs.call_price(S, K, T, R, SIG)
    assert bs.price_option(S, K, T, R, SIG, "CE") == bs.call_price(S, K, T, R, SIG)
    assert bs.price_option(S, K, T, R, SIG, "PE") == bs.put_price(S, K, T, R, SIG)
    assert bs.price_option(S, K, T, R, SIG, "pe") == bs.put_price(S, K, T, R, SIG)


def test_call_greeks_reference():
    g = bs.greeks(S, K, T, R, SIG, "CE")
    assert g.delta == pytest.approx(0.6368, abs=1e-4)
    assert g.gamma == pytest.approx(0.018762, abs=1e-6)
    assert g.vega == pytest.approx(0.3752, abs=1e-4)          # per 1% vol
    assert g.theta == pytest.approx(-6.414 / 365, abs=1e-4)   # per calendar day
    assert g.rho == pytest.approx(0.5323, abs=1e-4)           # per 1% rate


def test_put_greeks_relationships():
    c = bs.greeks(S, K, T, R, SIG, "CE")
    p = bs.greeks(S, K, T, R, SIG, "PE")
    assert p.delta == pytest.approx(c.delta - 1, abs=1e-4)
    assert p.gamma == c.gamma and p.vega == c.vega
    assert p.rho == pytest.approx(-0.4189, abs=1e-4)
    assert p.theta == pytest.approx(-1.6579 / 365, abs=1e-4)
    assert p.rho < 0 < c.rho


def test_greeks_zero_at_expiry_boundary():
    z = bs.greeks(S, K, 1e-6, R, SIG, "CE")
    assert (z.delta, z.gamma, z.theta, z.vega, z.rho) == (0.0, 0.0, 0.0, 0.0, 0.0)
    nz = bs.greeks(S, K, 2e-6, R, SIG, "CE")
    assert nz.gamma != 0.0 or nz.delta != 0.0


@pytest.mark.parametrize("opt", ["CE", "PE"])
@pytest.mark.parametrize("sigma", [0.1, 0.35, 0.8])
def test_implied_vol_round_trips(opt, sigma):
    px = bs.price_option(S, 105.0, 0.5, R, sigma, opt)
    iv = bs.implied_volatility(px, S, 105.0, 0.5, R, opt)
    assert iv == pytest.approx(sigma, abs=1e-4)


def test_implied_vol_guards():
    assert bs.implied_volatility(5.0, S, K, 0, R, "CE") is None
    assert bs.implied_volatility(5.0, S, K, -1, R, "CE") is None
    assert bs.implied_volatility(0, S, K, T, R, "CE") is None
    assert bs.implied_volatility(-1, S, K, T, R, "CE") is None


def test_implied_vol_non_convergence_returns_none():
    # price below intrinsic for a deep ITM call: no vol can produce it
    assert bs.implied_volatility(1.0, 200.0, 100.0, 0.5, R, "CE") is None
    # one iteration is not enough for an off-ATM price
    px = bs.price_option(S, 140.0, 0.5, R, 0.6, "CE")
    assert bs.implied_volatility(px, S, 140.0, 0.5, R, "CE", max_iterations=1) is None


def test_implied_vol_atm_and_otm_initial_guess_branches():
    px_atm = bs.price_option(S, S, 0.25, R, 0.3, "CE")
    assert bs.implied_volatility(px_atm, S, S, 0.25, R, "CE") == pytest.approx(0.3, abs=1e-4)
    px_otm = bs.price_option(S, 130.0, 0.25, R, 0.3, "CE")
    assert bs.implied_volatility(px_otm, S, 130.0, 0.25, R, "CE") == pytest.approx(0.3, abs=1e-4)


def test_implied_vol_rounded_to_six_places():
    px = bs.price_option(S, K, T, R, 0.2345678, "CE")
    iv = bs.implied_volatility(px, S, K, T, R, "CE")
    assert iv == round(iv, 6)


def _leg(**kw):
    base = dict(option_type="CE", action="BUY", strike=100.0, premium=5.0, lots=1, lot_size=1)
    base.update(kw)
    return base


def test_payoff_long_call_and_short_put():
    out = bs.payoff_at_expiry([_leg()], 80, 120, steps=4)
    assert [p["spot"] for p in out] == [80.0, 90.0, 100.0, 110.0, 120.0]
    assert [p["pnl"] for p in out] == [-5.0, -5.0, -5.0, 5.0, 15.0]
    out = bs.payoff_at_expiry([_leg(option_type="PE", action="SELL")], 80, 120, steps=4)
    assert [p["pnl"] for p in out] == [-15.0, -5.0, 5.0, 5.0, 5.0]


def test_payoff_futures_leg_and_multiplier_and_defaults():
    out = bs.payoff_at_expiry([dict(option_type="FUT", action="BUY", strike=100.0, premium=0.0,
                                    lots=2, lot_size=10)], 90, 110, steps=2)
    assert [p["pnl"] for p in out] == [-200.0, 0.0, 200.0]
    out = bs.payoff_at_expiry([dict(option_type="FUT", action="SELL", strike=100.0, premium=0.0)],
                              90, 110, steps=2)
    assert [p["pnl"] for p in out] == [10.0, 0.0, -10.0]       # lots/lot_size default to 1


def test_payoff_combined_legs_and_default_steps():
    straddle = [_leg(), _leg(option_type="PE")]
    out = bs.payoff_at_expiry(straddle, 50, 150)
    assert len(out) == 81
    assert min(p["pnl"] for p in out) == -10.0
    assert out[0]["pnl"] == 40.0 and out[-1]["pnl"] == 40.0
    # action / option_type are case-insensitive
    assert bs.payoff_at_expiry([_leg(action="buy", option_type="ce")], 100, 110, steps=1) == \
        bs.payoff_at_expiry([_leg()], 100, 110, steps=1)


# ── parity_engine: pure maths ────────────────────────────────────────────────

def test_discount_factor():
    assert pe.discount_factor(0.068, 0) == 1.0
    assert pe.discount_factor(0.068, 365) == pytest.approx(math.exp(-0.068))
    assert pe.discount_factor(0.0, 100) == 1.0


def test_theoretical_cp_spread():
    assert pe.theoretical_cp_spread(50100, 50000, 0.068, 0) == 100
    assert pe.theoretical_cp_spread(50100, 50000, 0.068, 365) == pytest.approx(100 * math.exp(-0.068))
    assert pe.theoretical_cp_spread(49900, 50000, 0.0, 30) == -100


def test_observed_cp_spread_by_direction():
    args = (110.0, 112.0, 60.0, 64.0)
    assert pe.observed_cp_spread(*args, "LONG_CALL_SHORT_PUT") == 112.0 - 60.0
    assert pe.observed_cp_spread(*args, "SHORT_CALL_LONG_PUT") == 110.0 - 64.0
    assert pe.observed_cp_spread(*args, "NONE") == 111.0 - 62.0
    assert pe.observed_cp_spread(*args, "anything") == 111.0 - 62.0


def test_estimate_transaction_cost_matches_hand_calc_nse():
    cfg = cfgmod.INSTRUMENTS["BANKNIFTY"]
    cm = cfgmod.COST_MODEL
    call_mid, put_mid, fut = 200.0, 150.0, 50000.0
    lot = 15
    notional = fut * lot            # multiplier == 1 -> lot size used
    brokerage = cm.brokerage_per_order * 6
    opt_stt = (call_mid * lot * cm.stt_options_sell_rate + put_mid * lot * cm.stt_options_sell_rate) * 2
    fut_stt = notional * cm.stt_futures_rate * 2
    exch = (call_mid + put_mid) * lot * cm.exchange_charge_nse * 2 + notional * cm.exchange_charge_nse * 2
    gst = (brokerage + exch) * cm.gst_rate
    sebi = (call_mid + put_mid) * lot * cm.sebi_rate * 2 + notional * cm.sebi_rate * 2
    per_lot = brokerage + opt_stt + fut_stt + exch + gst + sebi
    assert pe.estimate_transaction_cost(cfg, 1, call_mid, put_mid, fut) == pytest.approx(per_lot)
    assert pe.estimate_transaction_cost(cfg, 3, call_mid, put_mid, fut) == pytest.approx(3 * per_lot)


def test_estimate_transaction_cost_mcx_uses_multiplier_and_mcx_rate():
    cfg = cfgmod.INSTRUMENTS["CRUDEOIL"]
    cm = cfgmod.COST_MODEL
    call_mid, put_mid, fut = 100.0, 90.0, 6000.0
    notional = fut * cfg.contract_value_multiplier
    brokerage = cm.brokerage_per_order * 6
    opt_stt = (call_mid + put_mid) * cfg.lot_size * cm.stt_options_sell_rate * 2
    fut_stt = notional * cm.stt_futures_rate * 2
    exch = (call_mid + put_mid) * cfg.lot_size * cm.exchange_charge_mcx * 2 + notional * cm.exchange_charge_mcx * 2
    gst = (brokerage + exch) * cm.gst_rate
    sebi = (call_mid + put_mid) * cfg.lot_size * cm.sebi_rate * 2 + notional * cm.sebi_rate * 2
    assert pe.estimate_transaction_cost(cfg, 1, call_mid, put_mid, fut) == \
        pytest.approx(brokerage + opt_stt + fut_stt + exch + gst + sebi)


# ── parity_engine: ParityEngine ──────────────────────────────────────────────

class _FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 1, 1)


@pytest.fixture()
def eng(monkeypatch):
    monkeypatch.setattr(pe, "date", _FixedDate)
    return pe.ParityEngine(r=0.0)


def rec(strike, typ, bid, ask, oi=1000, sym=None):
    return {"strike": strike, "instrument_type": typ, "bid": bid, "ask": ask, "oi": oi,
            "tradingsymbol": sym or f"{typ}{int(strike)}"}


def chain(strike, call_mid, put_mid, spread=2.0, oi=1000):
    return [rec(strike, "CE", call_mid - spread / 2, call_mid + spread / 2, oi),
            rec(strike, "PE", put_mid - spread / 2, put_mid + spread / 2, oi)]


def test_default_rate_is_config_rate():
    assert pe.ParityEngine().r == cfgmod.RISK_FREE_RATE


def test_build_option_matrix_pairs_and_drops_incomplete(eng):
    rows = chain(50000, 300, 200) + [rec(50100, "CE", 1, 2)] + [rec(49900, "PE", 1, 2)]
    m = eng.build_option_matrix(rows)
    assert list(m) == [50000.0]
    r = m[50000.0]
    assert (r.call_bid, r.call_ask, r.put_bid, r.put_ask) == (299.0, 301.0, 199.0, 201.0)
    assert r.call_symbol == "CE50000" and r.put_symbol == "PE50000" and r.call_oi == 1000


def test_build_option_matrix_none_values_and_unknown_type(eng):
    rows = [{"strike": "50000", "instrument_type": "CE", "bid": None, "ask": None, "oi": None,
             "tradingsymbol": "C"},
            {"strike": "50000", "instrument_type": "PE", "tradingsymbol": "P"},
            {"strike": "50000", "instrument_type": "FUT", "bid": 9, "ask": 9, "tradingsymbol": "F"}]
    r = eng.build_option_matrix(rows)[50000.0]
    assert (r.call_bid, r.call_ask, r.call_oi, r.put_bid, r.put_oi) == (0.0, 0.0, 0, 0.0, 0)


def test_dte_calendar_days_floor(eng):
    assert eng._dte("2026-01-31") == 30.0
    assert eng._dte("2026-01-01") == 0.001
    assert eng._dte("2025-12-01") == 0.001      # past expiry floored


def test_liquidity_filter_requires_oi_and_two_sided_quotes(eng):
    cfg = cfgmod.INSTRUMENTS["BANKNIFTY"]
    base = dict(strike=1, call_bid=1, call_ask=2, call_oi=500, put_bid=1, put_ask=2, put_oi=500,
                call_symbol="c", put_symbol="p")
    ok = pe.OptionRow(**base)
    assert eng._liquidity_ok(ok, cfg, 500) is True            # >= boundary
    assert eng._liquidity_ok(ok, cfg, 501) is False
    for k in ("call_bid", "call_ask", "put_bid", "put_ask"):
        assert eng._liquidity_ok(pe.OptionRow(**{**base, k: 0}), cfg, 1) is False, k
    assert eng._liquidity_ok(pe.OptionRow(**{**base, "put_oi": 499}), cfg, 500) is False
    assert eng._liquidity_ok(pe.OptionRow(**{**base, "call_oi": 499}), cfg, 500) is False


def test_pick_lots_scales_and_caps(eng):
    cfg = cfgmod.INSTRUMENTS["BANKNIFTY"]       # min_dev 30, max_lots 50
    assert eng._pick_lots(cfg, 0.0) == 1
    assert eng._pick_lots(cfg, 29.0) == 1
    assert eng._pick_lots(cfg, 60.0) == 2
    assert eng._pick_lots(cfg, 89.9) == 2
    assert eng._pick_lots(cfg, 10_000.0) == 50


def test_scan_short_call_long_put_when_call_rich(eng):
    sigs = eng.scan("BANKNIFTY", chain(50000, 400, 200), 50000.0, "BNF-FUT", "2026-01-31")
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction == "SHORT_CALL_LONG_PUT"
    assert s.raw_deviation == pytest.approx(200.0) and s.theoretical_spread == 0.0
    assert s.observed_spread == 200.0 and s.dte == 30.0
    assert s.lots == 6                                    # int(200/30)
    assert s.net_deviation == pytest.approx(s.raw_deviation - s.transaction_cost)
    assert s.transaction_cost > 0
    assert (s.call_symbol, s.put_symbol, s.futures_symbol) == ("CE50000", "PE50000", "BNF-FUT")
    assert s.instrument == "BANKNIFTY" and s.expiry == "2026-01-31" and s.strike == 50000.0


def test_scan_long_call_short_put_when_put_rich(eng):
    sigs = eng.scan("BANKNIFTY", chain(50000, 200, 400), 50000.0, "F", "2026-01-31")
    assert sigs[0].direction == "LONG_CALL_SHORT_PUT"
    assert sigs[0].raw_deviation == pytest.approx(-200.0)


def test_scan_threshold_boundary_is_exclusive(eng):
    # |dev| == min_deviation (30) -> skipped; just above -> considered (but may be eaten by costs)
    assert eng.scan("BANKNIFTY", chain(50000, 230, 200), 50000.0, "F", "2026-01-31") == []
    assert eng.scan("BANKNIFTY", chain(50000, 200, 230), 50000.0, "F", "2026-01-31") == []


def test_scan_drops_signals_whose_cost_exceeds_deviation(eng):
    # deviation just above threshold on a huge-notional chain: costs swamp it
    sigs = eng.scan("BANKNIFTY", chain(50000, 231, 200), 5_000_000.0 + 50000, "F", "2026-01-31")
    # theoretical = F-K = 5e6; observed ~31 => dev hugely negative -> LONG dir, big abs dev; just ensure no crash
    assert all(s.net_deviation > 0 for s in sigs)
    cheap = eng.scan("BANKNIFTY", chain(50000, 231, 200), 50000.0, "F", "2026-01-31")
    assert cheap == [] or cheap[0].net_deviation > 0


def test_scan_skips_illiquid_and_respects_min_oi(eng):
    ch = chain(50000, 400, 200, oi=499)
    assert eng.scan("BANKNIFTY", ch, 50000.0, "F", "2026-01-31") == []
    assert len(eng.scan("BANKNIFTY", ch, 50000.0, "F", "2026-01-31", min_oi=499)) == 1


def test_scan_sorted_by_net_deviation_desc(eng):
    ch = chain(50000, 400, 200) + chain(50100, 700, 200) + chain(49900, 600, 200)
    sigs = eng.scan("BANKNIFTY", ch, 50000.0, "F", "2026-01-31")
    nets = [s.net_deviation for s in sigs]
    assert nets == sorted(nets, reverse=True) and len(sigs) == 3


def test_scan_uses_theoretical_spread_with_discounting(monkeypatch):
    monkeypatch.setattr(pe, "date", _FixedDate)
    e = pe.ParityEngine(r=0.10)
    # F-K = 100, dte 30 -> theoretical = 100*exp(-0.1*30/365); observed spread 100 => raw dev ~ +0.8 -> below threshold
    assert e.scan("BANKNIFTY", chain(50000, 300, 200), 50100.0, "F", "2026-01-31") == []
    # make observed 340 -> raw dev ~ 240.8, well above threshold and costs
    sigs = e.scan("BANKNIFTY", chain(50000, 540, 200), 50100.0, "F", "2026-01-31")
    th = 100 * math.exp(-0.1 * 30 / 365)
    assert sigs and sigs[0].theoretical_spread == pytest.approx(th)
    assert sigs[0].raw_deviation == pytest.approx(340 - th)


def test_scan_unknown_instrument_raises(eng):
    with pytest.raises(KeyError):
        eng.scan("NOPE", [], 1.0, "F", "2026-01-31")


def _signal(eng, strike=50000.0):
    return eng.scan("BANKNIFTY", chain(strike, 400, 200), 50000.0, "F", "2026-01-31")[0]


def test_check_exit_profit_target_and_stop_loss(eng):
    sig = _signal(eng)
    # entry deviation 200, exit_fraction .2 -> target 40; stop 2.5x -> 500
    def ex(call_mid, put_mid, fut=50000.0):
        return eng.check_exit(sig, call_mid - 1, call_mid + 1, put_mid - 1, put_mid + 1, fut,
                              entry_deviation=200.0, exit_fraction=0.2, stop_loss_multiple=2.5)
    ok, why = ex(240, 200)                      # dev 40 -> <= target
    assert ok and why.startswith("PROFIT_TARGET") and "dev=40.00" in why and "target=40.00" in why
    ok, why = ex(241, 200)                      # dev 41 -> hold
    assert (ok, why) == (False, "")
    ok, why = ex(700, 200)                      # dev 500 -> stop
    assert ok and why.startswith("STOP_LOSS") and "sl=500.00" in why
    assert ex(699, 200) == (False, "")


def test_check_exit_uses_absolute_entry_deviation(eng):
    sig = _signal(eng)
    ok, _ = eng.check_exit(sig, 99, 101, 99, 101, 50000.0, entry_deviation=-200.0,
                           exit_fraction=0.2, stop_loss_multiple=2.5)
    assert ok            # dev 0 <= 40 even with a negative entry deviation


# ── bayesian_threshold ───────────────────────────────────────────────────────

def test_tracker_starts_at_prior_and_base_threshold():
    t = bt.BayesianThresholdTracker(base_threshold=30.0)
    assert t.posterior() == (1.0, 1.0)
    assert t.posterior_mean() == 0.5
    assert t.recommended_threshold() == 30.0


def test_observe_updates_counts_without_discount():
    t = bt.BayesianThresholdTracker(base_threshold=30.0)
    t.observe(31, True)
    t.observe(31, True)
    t.observe(31, False)
    assert t.posterior() == (3.0, 2.0)
    assert t.posterior_mean() == pytest.approx(0.6)


def test_observe_discounts_before_adding():
    t = bt.BayesianThresholdTracker(base_threshold=30.0, discount_factor=0.5)
    t.observe(0, True)         # a = 1*.5+1 = 1.5 ; b = 1*.5 = .5
    assert t.posterior() == (1.5, 0.5)
    t.observe(0, False)        # a = .75 ; b = .25+1
    assert t.posterior() == (0.75, 1.25)


def test_custom_prior_used():
    t = bt.BayesianThresholdTracker(base_threshold=1.0, prior_alpha=5.0, prior_beta=2.0)
    assert t.posterior() == (5.0, 2.0)


def test_recommended_threshold_tightens_when_losing_and_is_capped():
    t = bt.BayesianThresholdTracker(base_threshold=30.0)
    for _ in range(5):
        t.observe(0, False)
    assert t.recommended_threshold() == 33.0            # 30 * 1.1
    assert t.recommended_threshold() == 36.3            # compounding per call
    for _ in range(200):
        t.recommended_threshold()
    assert t.recommended_threshold() == 90.0            # cap = 3x base


def test_recommended_threshold_relaxes_when_winning_and_is_floored():
    t = bt.BayesianThresholdTracker(base_threshold=30.0)
    for _ in range(5):
        t.observe(0, True)
    assert t.recommended_threshold() == 27.0
    for _ in range(200):
        t.recommended_threshold()
    assert t.recommended_threshold() == 15.0            # floor = 0.5x base


def test_confidence_target_boundary_counts_as_comfortable():
    t = bt.BayesianThresholdTracker(base_threshold=100.0, prior_alpha=0, prior_beta=0,
                                    confidence_target=0.5)
    t.observe(0, True)
    t.observe(0, False)                                  # mean exactly 0.5 -> relax
    assert t.recommended_threshold() == 90.0


def test_adjustment_step_and_fractions_configurable():
    t = bt.BayesianThresholdTracker(base_threshold=100.0, adjustment_step=0.5,
                                    max_threshold_fraction=1.6)
    t.observe(0, False)
    assert t.recommended_threshold() == 150.0
    assert t.recommended_threshold() == 160.0            # capped at 1.6x


def test_reset_horizon_clears_everything():
    t = bt.BayesianThresholdTracker(base_threshold=30.0, prior_alpha=2.0, prior_beta=3.0)
    for _ in range(4):
        t.observe(0, False)
    t.recommended_threshold()
    t.reset_horizon()
    assert t.posterior() == (2.0, 3.0)
    assert t.recommended_threshold() == 30.0
    t.observe(0, True)
    t.reset_horizon()
    assert t._n_observed == 0 and t._multiplier == 1.0


def test_credible_interval_brackets_mean_and_widens_with_width():
    t = bt.BayesianThresholdTracker(base_threshold=30.0)
    for i in range(20):
        t.observe(0, i % 4 != 0)
    lo90, hi90 = t.credible_interval()
    lo50, hi50 = t.credible_interval(0.5)
    assert lo90 < t.posterior_mean() < hi90
    assert lo90 < lo50 < hi50 < hi90
    assert 0 <= lo90 and hi90 <= 1


def test_build_trackers_for_all_instruments():
    ts = bt.build_trackers_for_all_instruments(discount_factor=0.9)
    assert set(ts) == set(cfgmod.INSTRUMENTS)
    for k, tr in ts.items():
        assert tr.base_threshold == cfgmod.INSTRUMENTS[k].min_deviation
        assert tr.discount_factor == 0.9
    ts["SILVER"].observe(0, False)
    assert ts["BANKNIFTY"]._n_observed == 0               # independent trackers
    assert bt.build_trackers_for_all_instruments()["BANKNIFTY"].discount_factor == 1.0
