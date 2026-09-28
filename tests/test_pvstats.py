"""불균형 지표와 ROC 함수를 검증합니다."""
import math

from _fv import pvstats


def test_two_by_two_matches_hand_calculation():
    s = pvstats.two_by_two(a=20, n_drug=1000, n_event=2000, N=1_000_000)
    prr = (20 / 1000) / (1980 / 999000)
    assert math.isclose(s["prr"], prr, rel_tol=1e-9)
    assert s["evans"] and s["triple"] and s["ic025"] > 0


def test_zero_cases_is_not_a_signal():
    s = pvstats.two_by_two(a=0, n_drug=1000, n_event=2000, N=1_000_000)
    assert s["prr"] is None and not s["triple"] and s["ic025"] < 0


def test_auc_basic_and_ties():
    assert pvstats.auc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) == 1.0
    assert pvstats.auc([0.5, 0.5], [1, 0]) == 0.5


def test_roc_points_monotone():
    pts = pvstats.roc_points([0.9, 0.7, 0.4, 0.2, 0.1], [1, 0, 1, 0, 0])
    assert pts[0] == [0.0, 0.0] and pts[-1] == [1.0, 1.0]
    assert all(b[0] >= a[0] and b[1] >= a[1] for a, b in zip(pts, pts[1:]))


def test_sens_spec():
    r = pvstats.sens_spec([True, False, True, False], [1, 1, 0, 0])
    assert r["sens"] == 0.5 and r["spec"] == 0.5
