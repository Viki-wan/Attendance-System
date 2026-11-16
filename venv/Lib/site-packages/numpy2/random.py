"""
numpy2.random - Pure-Python random number generation

Mirrors the numpy.random API using Python's stdlib random module.
No NumPy required.
"""

import random as _random
import math
import warnings as _warnings
from .array import ndarray, _dtype_cls, _prod


# ── global RNG state ──────────────────────────────────────────────────────────

_rng = _random.Random()

# Legacy RNG warning message
_LEGACY_RNG_WARNING = (
    "Legacy RandomState (Mersenne Twister) is deprecated. "
    "Use numpy2.random.Generator with default_rng() instead."
)


def seed(s=None):
    _warnings.warn(_LEGACY_RNG_WARNING, FutureWarning, stacklevel=2)
    _rng.seed(s)

def get_state():
    _warnings.warn(_LEGACY_RNG_WARNING, FutureWarning, stacklevel=2)
    return _rng.getstate()

def set_state(state):
    _warnings.warn(_LEGACY_RNG_WARNING, FutureWarning, stacklevel=2)
    _rng.setstate(state)


# ── shape helper ──────────────────────────────────────────────────────────────

def _make_shape(size):
    if size is None:
        return ()
    if isinstance(size, int):
        return (size,)
    return tuple(size)

def _fill(fn, shape):
    n = _prod(shape) if shape else 1
    data = [fn() for _ in range(n)]
    if not shape:
        return data[0]
    return ndarray(data, dtype=_dtype_cls('float64'), shape=shape)


# ── uniform distributions ─────────────────────────────────────────────────────

def _legacy_warning():
    _warnings.warn(_LEGACY_RNG_WARNING, FutureWarning, stacklevel=3)

def rand(*shape):
    """Uniform [0, 1) — rand(d0, d1, ...)"""
    _legacy_warning()
    if not shape:
        return _rng.random()
    n = _prod(shape)
    return ndarray([_rng.random() for _ in range(n)], dtype=_dtype_cls('float64'), shape=shape)

def random(size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(_rng.random, shape)

random_sample = random
ranf          = random
sample        = random

def random_integers(low, high=None, size=None):
    _legacy_warning()
    if high is None:
        high, low = low, 1
    shape = _make_shape(size)
    return _fill(lambda: _rng.randint(low, high), shape) if shape else _rng.randint(low, high)

def randint(low, high=None, size=None, dtype='int64'):
    _legacy_warning()
    if high is None:
        high, low = low, 0
    shape = _make_shape(size)
    fn = lambda: _rng.randint(low, high - 1)
    result = _fill(fn, shape)
    if isinstance(result, ndarray):
        return result.astype(dtype)
    return result

def uniform(low=0.0, high=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.uniform(low, high), shape)

def choice(a, size=None, replace=True, p=None):
    _legacy_warning()
    if isinstance(a, int):
        population = list(range(a))
    else:
        from .array import asarray
        population = list(asarray(a)._data)
    shape = _make_shape(size)
    n = _prod(shape) if shape else 1
    if p is not None:
        from .array import asarray
        weights = list(asarray(p)._data)
        chosen = _random.choices(population, weights=weights, k=n)
    elif replace:
        chosen = [_rng.choice(population) for _ in range(n)]
    else:
        chosen = _rng.sample(population, n)
    if not shape:
        return chosen[0]
    return ndarray(chosen, dtype=_dtype_cls('float64'), shape=shape)

def permutation(x):
    _legacy_warning()
    if isinstance(x, int):
        lst = list(range(x))
    else:
        from .array import asarray
        lst = list(asarray(x)._data)
    _rng.shuffle(lst)
    return ndarray(lst, dtype=_dtype_cls('float64'))

def shuffle(x):
    _legacy_warning()
    from .array import asarray
    a = asarray(x) if not isinstance(x, ndarray) else x
    _rng.shuffle(a._data)


# ── normal / Gaussian ─────────────────────────────────────────────────────────

def randn(*shape):
    """Standard normal N(0,1) — randn(d0, d1, ...)"""
    _legacy_warning()
    if not shape:
        return _rng.gauss(0, 1)
    n = _prod(shape)
    return ndarray([_rng.gauss(0, 1) for _ in range(n)],
                   dtype=_dtype_cls('float64'), shape=shape)

def standard_normal(size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.gauss(0, 1), shape)

def normal(loc=0.0, scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.gauss(loc, scale), shape)

def multivariate_normal(mean, cov, size=None):
    """Sample from multivariate normal using Cholesky decomposition."""
    _legacy_warning()
    from .array import asarray
    from .linalg import cholesky
    mean = asarray(mean)
    cov  = asarray(cov)
    n = len(mean._data)
    L = cholesky(cov)
    shape = _make_shape(size)
    num_samples = _prod(shape) if shape else 1
    result = []
    for _ in range(num_samples):
        z = [_rng.gauss(0, 1) for _ in range(n)]
        # x = mean + L @ z
        x = [mean._data[i] + sum(L._data[i*n+j] * z[j] for j in range(i+1))
             for i in range(n)]
        result.extend(x)
    final_shape = (tuple(shape) + (n,)) if shape else (n,)
    return ndarray(result, dtype=_dtype_cls('float64'), shape=final_shape)


# ── other continuous distributions ───────────────────────────────────────────

def exponential(scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.expovariate(1.0 / scale), shape)

def gamma(shape_param, scale=1.0, size=None):
    _legacy_warning()
    shp = _make_shape(size)
    return _fill(lambda: _rng.gammavariate(shape_param, scale), shp)

def beta(a, b, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.betavariate(a, b), shape)

def chisquare(df, size=None):
    _legacy_warning()
    return gamma(df / 2.0, 2.0, size=size)

def noncentral_chisquare(df, nonc, size=None):
    _legacy_warning()
    # Approximation: normal shift
    return chisquare(df, size=size)

def f(dfnum, dfden, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _f_sample():
        x1 = sum(_rng.gauss(0,1)**2 for _ in range(int(dfnum))) / dfnum
        x2 = sum(_rng.gauss(0,1)**2 for _ in range(int(dfden))) / dfden
        return x1 / x2 if x2 != 0 else float('inf')
    return _fill(_f_sample, shape)

def standard_t(df, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _t():
        z = _rng.gauss(0, 1)
        v = sum(_rng.gauss(0,1)**2 for _ in range(int(df)))
        return z / math.sqrt(v / df) if v > 0 else 0.0
    return _fill(_t, shape)

t = standard_t  # alias sometimes used

def lognormal(mean=0.0, sigma=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.lognormvariate(mean, sigma), shape)

def logistic(loc=0.0, scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _logistic():
        u = _rng.random()
        return loc + scale * math.log(u / (1 - u))
    return _fill(_logistic, shape)

def laplace(loc=0.0, scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _laplace():
        u = _rng.random() - 0.5
        return loc - scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))
    return _fill(_laplace, shape)

def gumbel(loc=0.0, scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _gumbel():
        u = _rng.random()
        return loc - scale * math.log(-math.log(u)) if u > 0 else float('inf')
    return _fill(_gumbel, shape)

def wald(mean, scale, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.gauss(mean, math.sqrt(scale)), shape)

def weibull(a, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.weibullvariate(1.0, a), shape)

def power(a, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.random() ** (1.0 / a), shape)

def triangular(left=0.0, mode=0.5, right=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.triangular(left, right, mode), shape)

def vonmises(mu=0.0, kappa=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.vonmisesvariate(mu, kappa), shape)

def rayleigh(scale=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: scale * math.sqrt(-2 * math.log(_rng.random())), shape)

def pareto(a, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: _rng.paretovariate(a) - 1, shape)

def zipf(a, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    # Acceptance-rejection for Zipf distribution
    def _zipf():
        b = 2 ** (a - 1)
        while True:
            u = _rng.random()
            x = int(u ** (-1 / (a - 1)))
            if x < 1:
                continue
            t = (1 + 1/x) ** (a - 1)
            v = _rng.random()
            if v * x * (t - 1) / (b - 1) <= t / b:
                return x
    return _fill(_zipf, shape)


# ── discrete distributions ────────────────────────────────────────────────────

def poisson(lam=1.0, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _poisson():
        L = math.exp(-lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= _rng.random()
        return k - 1
    return _fill(_poisson, shape)

def binomial(n, p, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: sum(1 for _ in range(n) if _rng.random() < p), shape)

def negative_binomial(n, p, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _nb():
        successes, trials = 0, 0
        while successes < n:
            if _rng.random() < p:
                successes += 1
            trials += 1
        return trials - n
    return _fill(_nb, shape)

def geometric(p, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    return _fill(lambda: math.ceil(math.log(_rng.random()) / math.log(1-p)), shape)

def hypergeometric(ngood, nbad, nsample, size=None):
    _legacy_warning()
    shape = _make_shape(size)
    def _hg():
        good, bad, drawn = ngood, nbad, nsample
        count = 0
        for _ in range(drawn):
            if _rng.random() < good / (good + bad):
                count += 1
                good -= 1
            else:
                bad -= 1
        return count
    return _fill(_hg, shape)

def multinomial(n, pvals, size=None):
    _legacy_warning()
    from .array import asarray
    pvals = list(asarray(pvals)._data)
    shape = _make_shape(size) or ()
    def _sample():
        counts = [0] * len(pvals)
        cumulative = []
        s = 0
        for p in pvals:
            s += p
            cumulative.append(s)
        for _ in range(n):
            u = _rng.random()
            for i, c in enumerate(cumulative):
                if u <= c:
                    counts[i] += 1
                    break
        return counts
    if not shape:
        return ndarray(_sample(), dtype=_dtype_cls('int64'))
    result = []
    for _ in range(_prod(shape)):
        result.extend(_sample())
    return ndarray(result, dtype=_dtype_cls('int64'),
                   shape=shape + (len(pvals),))

def dirichlet(alpha, size=None):
    _legacy_warning()
    alpha = list(alpha)
    shape = _make_shape(size) or ()
    def _sample():
        gammas = [_rng.gammavariate(a, 1) for a in alpha]
        s = sum(gammas)
        return [g / s for g in gammas]
    if not shape:
        return ndarray(_sample(), dtype=_dtype_cls('float64'))
    result = []
    for _ in range(_prod(shape)):
        result.extend(_sample())
    return ndarray(result, dtype=_dtype_cls('float64'),
                   shape=shape + (len(alpha),))


# ── Generator class (numpy 1.17+ style) ──────────────────────────────────────

class Generator:
    """numpy.random.Generator-compatible interface."""

    def __init__(self, rng=None):
        self._rng = _random.Random() if rng is None else rng

    def random(self, size=None):
        shape = _make_shape(size)
        return _fill(self._rng.random, shape)

    def integers(self, low, high=None, size=None, dtype='int64', endpoint=False):
        if high is None:
            high, low = low, 0
        if endpoint:
            high += 1
        shape = _make_shape(size)
        fn = lambda: self._rng.randint(low, high - 1)
        return _fill(fn, shape)

    def normal(self, loc=0.0, scale=1.0, size=None):
        shape = _make_shape(size)
        return _fill(lambda: self._rng.gauss(loc, scale), shape)

    def uniform(self, low=0.0, high=1.0, size=None):
        shape = _make_shape(size)
        return _fill(lambda: self._rng.uniform(low, high), shape)

    def choice(self, a, size=None, replace=True, p=None, axis=0, shuffle=True):
        return choice(a, size=size, replace=replace, p=p)

    def shuffle(self, x, axis=0):
        shuffle(x)

    def permutation(self, x):
        return permutation(x)

    def standard_normal(self, size=None):
        return self.normal(size=size)

    def exponential(self, scale=1.0, size=None):
        return exponential(scale, size=size)


class BitGenerator:
    """Minimal BitGenerator stub."""
    def __init__(self, seed=None):
        self._rng = _random.Random(seed)


class PCG64(BitGenerator):
    pass

class MT19937(BitGenerator):
    pass

class Philox(BitGenerator):
    pass

class SFC64(BitGenerator):
    pass


def default_rng(seed=None):
    rng = _random.Random(seed)
    return Generator(rng)


# ── module-level convenience aliases ─────────────────────────────────────────
standard_cauchy   = lambda size=None: standard_t(1, size=size)
standard_gamma    = lambda shape, size=None: gamma(shape, 1.0, size=size)
standard_exponential = lambda size=None: exponential(1.0, size=size)
