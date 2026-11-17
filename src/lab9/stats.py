"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    pairs = list(zip(human, judge))
    return {"tp": sum(h == POS and j == POS for h, j in pairs),
            "fp": sum(h != POS and j == POS for h, j in pairs),
            "fn": sum(h == POS and j != POS for h, j in pairs),
            "tn": sum(h != POS and j != POS for h, j in pairs)}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    c = confusion(human, judge)
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    return p, r


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    c = confusion(human, judge)
    n = sum(c.values())
    if n == 0:
        raise ValueError("kappa undefined: no labels")
    p_o = (c["tp"] + c["tn"]) / n
    p_e = ((c["tp"] + c["fp"]) * (c["tp"] + c["fn"]) + (c["tn"] + c["fn"]) * (c["tn"] + c["fp"])) / n**2
    if p_e == 1:
        raise ValueError("kappa undefined: chance agreement is 1")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1
    if denom == 0:
        raise ValueError("Rogan-Gladen undefined: sensitivity + specificity == 1 (judge no better than chance)")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denom))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy import stats as sps

    a_, b_ = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a_.shape != b_.shape or a_.size == 0:
        raise ValueError("a and b must be the same non-zero length")
    if np.array_equal(a_, b_):
        return 0.0, 0.0, 0.0
    res = sps.bootstrap((a_, b_), lambda x, y, axis: np.mean(x, axis=axis) - np.mean(y, axis=axis), paired=True,
                        vectorized=True, n_resamples=n_resamples, confidence_level=confidence,
                        method="percentile", rng=np.random.default_rng(rng))
    ci = res.confidence_interval
    return float(a_.mean() - b_.mean()), float(ci.low), float(ci.high)


def _check_nck(n: int, c: int, k: int) -> None:
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if n < 1 or k < 1 or k > n or c < 0 or c > n:
        raise ValueError(f"need n >= 1, 1 <= k <= n, 0 <= c <= n; got n={n}, c={c}, k={k}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_nck(n, c, k)
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_nck(n, c, k)
    return comb(c, k) / comb(n, k)
