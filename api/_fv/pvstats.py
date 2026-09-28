"""약물감시 통계 함수입니다. 웨어하우스 SQL(model.sql)과 같은 공식을 파이썬으로 옮겼습니다.
파이프라인·API·테스트가 같은 함수를 씁니다. 외부 호출이 없습니다."""
import math
import random


def two_by_two(a: float, n_drug: float, n_event: float, N: float) -> dict:
    """a: 약물과 반응이 함께 보고된 케이스, n_drug: 약물 케이스, n_event: 반응 케이스, N: 전체 케이스.
    PRR·ROR 95% CI, Yates 카이제곱, BCPNN IC 와 IC025, Evans 신호, 세 기준 동시 충족 여부를 돌려줍니다."""
    b, c = n_drug - a, n_event - a
    d = N - n_drug - n_event + a
    E = n_drug * n_event / N if N else 0.0
    out = {"a": int(a), "expected": E, "prr": None, "prr_lo": None, "prr_hi": None, "ror": None, "ror_lo": None,
           "chi2": 0.0, "ic": None, "ic025": None, "evans": False, "ror_sig": False, "ic_sig": False, "triple": False}
    out["ic"] = math.log2((a + 0.5) / (E + 0.5))
    out["ic025"] = out["ic"] - 3.3 * (a + 0.5) ** -0.5 - 2 * (a + 0.5) ** -1.5
    if a > 0 and b > 0 and c > 0 and d > 0:
        prr = (a / (a + b)) / (c / (c + d))
        se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
        ror = (a * d) / (b * c)
        se_r = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        chi2 = N * max(abs(a * d - b * c) - N / 2, 0) ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))
        out.update(prr=prr, prr_lo=math.exp(math.log(prr) - 1.96 * se), prr_hi=math.exp(math.log(prr) + 1.96 * se),
                   ror=ror, ror_lo=math.exp(math.log(ror) - 1.96 * se_r), chi2=chi2)
        out["evans"] = prr >= 2 and chi2 >= 4 and a >= 3
        out["ror_sig"] = out["ror_lo"] > 1 and a >= 3
    out["ic_sig"] = out["ic025"] > 0
    out["triple"] = out["evans"] and out["ror_sig"] and out["ic_sig"]
    return out


def auc(scores: list[float], labels: list[int]) -> float | None:
    """Mann-Whitney AUC 를 순위합으로 계산합니다(동점은 평균 순위). O(n log n) 입니다."""
    P = sum(labels)
    Nn = len(labels) - P
    if not P or not Nn:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    rp = sum(r for r, y in zip(ranks, labels) if y == 1)
    return (rp - P * (P + 1) / 2) / (P * Nn)


def roc_points(scores: list[float], labels: list[int], max_points: int = 120) -> list[list[float]]:
    """임계값을 내려가며 (FPR, TPR) 을 모읍니다. 동점은 한 번에 처리합니다."""
    P = sum(labels)
    Nn = len(labels) - P
    if not P or not Nn:
        return []
    pairs = sorted(zip(scores, labels), key=lambda t: -t[0])
    pts, tp, fp, i = [[0.0, 0.0]], 0, 0, 0
    while i < len(pairs):
        s = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == s:
            tp += pairs[i][1]
            fp += 1 - pairs[i][1]
            i += 1
        pts.append([fp / Nn, tp / P])
    if len(pts) > max_points:
        step = len(pts) / max_points
        pts = [pts[int(k * step)] for k in range(max_points)] + [pts[-1]]
    return [[round(x, 4), round(y, 4)] for x, y in pts]


def sens_spec(flags: list[bool], labels: list[int]) -> dict:
    tp = sum(1 for f, y in zip(flags, labels) if f and y == 1)
    fn = sum(1 for f, y in zip(flags, labels) if not f and y == 1)
    tn = sum(1 for f, y in zip(flags, labels) if not f and y == 0)
    fp = sum(1 for f, y in zip(flags, labels) if f and y == 0)
    return {"sens": tp / (tp + fn) if tp + fn else None, "spec": tn / (tn + fp) if tn + fp else None,
            "ppv": tp / (tp + fp) if tp + fp else None, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def bootstrap_auc(scores: list[float], labels: list[int], n: int = 2000, seed: int = 20260928) -> list[float] | None:
    """층화 부트스트랩 95% 구간입니다."""
    rng = random.Random(seed)
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if len(pos) < 2 or len(neg) < 2:
        return None
    vals = []
    for _ in range(n):
        p = [rng.choice(pos) for _ in pos]
        q = [rng.choice(neg) for _ in neg]
        vals.append(auc(p + q, [1] * len(p) + [0] * len(q)))
    vals.sort()
    return [round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n)], 4)]


def bootstrap_delta(sa: list[float], sb: list[float], labels: list[int], n: int = 2000, seed: int = 7) -> dict:
    """같은 쌍에서 두 방법의 AUC 차이(sa - sb)와 짝지은 부트스트랩 95% 구간입니다."""
    rng = random.Random(seed)
    idx_p = [i for i, y in enumerate(labels) if y == 1]
    idx_n = [i for i, y in enumerate(labels) if y == 0]
    base = auc(sa, labels) - auc(sb, labels)
    vals = []
    for _ in range(n):
        ii = [rng.choice(idx_p) for _ in idx_p] + [rng.choice(idx_n) for _ in idx_n]
        yy = [labels[i] for i in ii]
        vals.append(auc([sa[i] for i in ii], yy) - auc([sb[i] for i in ii], yy))
    vals.sort()
    return {"delta": round(base, 4), "ci": [round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n)], 4)]}
