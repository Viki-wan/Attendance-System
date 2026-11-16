"""
numpy2.math_ops - Pure-Python ufuncs and math operations

All functions work on scalars, lists, or numpy2 ndarrays.
NumPy is NOT required.
"""

import math
import cmath
import operator
from .array import ndarray, asarray, _dtype_cls, zeros, _prod, _broadcast_to, _broadcast_shapes

# ── ufunc factory ─────────────────────────────────────────────────────────────

def _ufunc1(fn, out_dtype='float64'):
    """Build a unary ufunc."""
    def _f(x, out=None):
        if isinstance(x, ndarray):
            result = ndarray([fn(v) for v in x._data],
                             dtype=_dtype_cls(out_dtype), shape=x._shape)
        else:
            result = fn(x)
        if out is not None and isinstance(out, ndarray):
            out._data = result._data if isinstance(result, ndarray) else [result]
        return result
    return _f

def _ufunc2(fn, out_dtype='float64'):
    """Build a binary ufunc."""
    def _f(x, y, out=None):
        x = asarray(x) if not isinstance(x, (int, float, complex, bool)) else x
        y = asarray(y) if not isinstance(y, (int, float, complex, bool)) else y
        if isinstance(x, ndarray) and isinstance(y, ndarray):
            if x._shape != y._shape:
                bs = _broadcast_shapes(x._shape, y._shape)
                x = _broadcast_to(x, bs)
                y = _broadcast_to(y, bs)
            result = ndarray([fn(a, b) for a, b in zip(x._data, y._data)],
                             dtype=_dtype_cls(out_dtype), shape=x._shape)
        elif isinstance(x, ndarray):
            result = ndarray([fn(v, y) for v in x._data],
                             dtype=_dtype_cls(out_dtype), shape=x._shape)
        elif isinstance(y, ndarray):
            result = ndarray([fn(x, v) for v in y._data],
                             dtype=_dtype_cls(out_dtype), shape=y._shape)
        else:
            result = fn(x, y)
        if out is not None and isinstance(out, ndarray):
            out._data = result._data if isinstance(result, ndarray) else [result]
        return result
    return _f


# ── safe scalar math ──────────────────────────────────────────────────────────

def _safe_sqrt(x):
    if isinstance(x, complex):
        return cmath.sqrt(x)
    if x < 0:
        return complex(0, math.sqrt(-x))
    return math.sqrt(x)

def _safe_log(x):
    if isinstance(x, complex):
        return cmath.log(x)
    if x <= 0:
        return float('-inf') if x == 0 else float('nan')
    return math.log(x)

def _safe_log2(x):
    if x <= 0:
        return float('-inf') if x == 0 else float('nan')
    return math.log2(x)

def _safe_log10(x):
    if x <= 0:
        return float('-inf') if x == 0 else float('nan')
    return math.log10(x)

def _safe_log1p(x):
    if x <= -1:
        return float('-inf') if x == -1 else float('nan')
    return math.log1p(x)

def _safe_arcsin(x):
    try:
        return math.asin(x)
    except ValueError:
        return float('nan')

def _safe_arccos(x):
    try:
        return math.acos(x)
    except ValueError:
        return float('nan')

def _safe_power(x, y):
    try:
        return x ** y
    except (ValueError, ZeroDivisionError):
        return float('nan')

def _fmod(x, y):
    return math.fmod(x, y) if y != 0 else float('nan')

def _divmod(x, y):
    return divmod(x, y)


# ── trigonometric ─────────────────────────────────────────────────────────────
sin    = _ufunc1(math.sin)
cos    = _ufunc1(math.cos)
tan    = _ufunc1(math.tan)
arcsin = _ufunc1(_safe_arcsin)
arccos = _ufunc1(_safe_arccos)
arctan = _ufunc1(math.atan)
arctan2= _ufunc2(math.atan2)
hypot  = _ufunc2(math.hypot)
deg2rad= _ufunc1(math.radians)
rad2deg= _ufunc1(math.degrees)
degrees= _ufunc1(math.degrees)
radians= _ufunc1(math.radians)
unwrap = None  # deferred

def _unwrap(p, discont=None, axis=-1, period=6.283185307179586):
    p = asarray(p)
    if discont is None:
        discont = period / 2
    out = list(p._data)
    for i in range(1, len(out)):
        diff = out[i] - out[i-1]
        if diff > discont:
            out[i] -= period * round(diff / period)
        elif diff < -discont:
            out[i] += period * round(-diff / period)
    return ndarray(out, dtype=p.dtype, shape=p._shape)
unwrap = _unwrap


# ── hyperbolic ────────────────────────────────────────────────────────────────
sinh    = _ufunc1(math.sinh)
cosh    = _ufunc1(math.cosh)
tanh    = _ufunc1(math.tanh)
arcsinh = _ufunc1(math.asinh)
arccosh = _ufunc1(lambda x: math.acosh(x) if x >= 1 else float('nan'))
arctanh = _ufunc1(lambda x: math.atanh(x) if -1 < x < 1 else float('nan'))


# ── exponential / logarithm ───────────────────────────────────────────────────
exp    = _ufunc1(math.exp)
exp2   = _ufunc1(lambda x: 2.0 ** x)
expm1  = _ufunc1(math.expm1)
log    = _ufunc1(_safe_log)
log2   = _ufunc1(_safe_log2)
log10  = _ufunc1(_safe_log10)
log1p  = _ufunc1(_safe_log1p)


# ── rounding ──────────────────────────────────────────────────────────────────
floor   = _ufunc1(math.floor, 'float64')
ceil    = _ufunc1(math.ceil,  'float64')
trunc   = _ufunc1(math.trunc, 'float64')
rint    = _ufunc1(lambda x: float(round(x)), 'float64')
fix     = _ufunc1(lambda x: math.trunc(x), 'float64')

def around(a, decimals=0, out=None):
    a = asarray(a)
    return ndarray([round(v, decimals) for v in a._data], dtype=a.dtype, shape=a._shape)

round_ = around


# ── arithmetic ─────────────────────────────────────────────────────────────────
add      = _ufunc2(operator.add)
subtract = _ufunc2(operator.sub)
multiply = _ufunc2(operator.mul)
divide   = _ufunc2(lambda a, b: a / b if b != 0 else (float('inf') if a > 0 else float('-inf') if a < 0 else float('nan')))
true_divide   = divide
floor_divide  = _ufunc2(operator.floordiv)
negative = _ufunc1(operator.neg)
positive = _ufunc1(operator.pos)
power    = _ufunc2(_safe_power)
float_power = _ufunc2(lambda x, y: float(x) ** float(y))
remainder    = _ufunc2(operator.mod)
mod          = remainder
fmod         = _ufunc2(_fmod)
absolute     = _ufunc1(abs)
abs          = absolute
fabs         = _ufunc1(lambda x: math.fabs(x))
sign         = _ufunc1(lambda x: (1 if x > 0 else -1 if x < 0 else 0))
heaviside    = _ufunc2(lambda x, h: 0.0 if x < 0 else (float(h) if x == 0 else 1.0))
sqrt         = _ufunc1(_safe_sqrt)
cbrt         = _ufunc1(lambda x: x**(1/3) if x >= 0 else -((-x)**(1/3)))
square       = _ufunc1(lambda x: x * x)
reciprocal   = _ufunc1(lambda x: 1.0 / x if x != 0 else float('inf'))


# ── logical ───────────────────────────────────────────────────────────────────
logical_and  = _ufunc2(lambda a, b: bool(a) and bool(b), 'bool')
logical_or   = _ufunc2(lambda a, b: bool(a) or  bool(b), 'bool')
logical_xor  = _ufunc2(lambda a, b: bool(a) ^   bool(b), 'bool')
logical_not  = _ufunc1(lambda a: not bool(a), 'bool')


# ── bitwise ───────────────────────────────────────────────────────────────────
bitwise_and    = _ufunc2(operator.and_,    'int64')
bitwise_or     = _ufunc2(operator.or_,     'int64')
bitwise_xor    = _ufunc2(operator.xor,     'int64')
bitwise_not    = _ufunc1(lambda x: ~int(x), 'int64')
invert         = bitwise_not
left_shift     = _ufunc2(operator.lshift,  'int64')
right_shift    = _ufunc2(operator.rshift,  'int64')


# ── comparison ────────────────────────────────────────────────────────────────
greater       = _ufunc2(operator.gt,  'bool')
greater_equal = _ufunc2(operator.ge,  'bool')
less          = _ufunc2(operator.lt,  'bool')
less_equal    = _ufunc2(operator.le,  'bool')
equal         = _ufunc2(operator.eq,  'bool')
not_equal     = _ufunc2(operator.ne,  'bool')
maximum       = _ufunc2(max)
minimum       = _ufunc2(min)
fmax          = _ufunc2(lambda a, b: b if (isinstance(a, float) and math.isnan(a)) else (a if (isinstance(b, float) and math.isnan(b)) else max(a, b)))
fmin          = _ufunc2(lambda a, b: b if (isinstance(a, float) and math.isnan(a)) else (a if (isinstance(b, float) and math.isnan(b)) else min(a, b)))
clip          = _ufunc1(lambda x: x)  # real clip below


def clip(a, a_min, a_max, out=None):
    a = asarray(a)
    return a.clip(a_min, a_max)


# ── complex ───────────────────────────────────────────────────────────────────
def real(a):
    a = asarray(a)
    return a.real

def imag(a):
    a = asarray(a)
    return a.imag

def conj(a):
    return asarray(a).conj()
conjugate = conj

def angle(z, deg=False):
    z = asarray(z)
    out = [math.degrees(cmath.phase(complex(v))) if deg else cmath.phase(complex(v))
           for v in z._data]
    return ndarray(out, dtype=_dtype_cls('float64'), shape=z._shape)

def absolute(x, out=None):
    x = asarray(x)
    return ndarray([abs(v) for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)
abs = absolute


# ── reductions ────────────────────────────────────────────────────────────────
def sum(a, axis=None, dtype=None, out=None, keepdims=False, initial=0):
    a = asarray(a)
    return a.sum(axis=axis, dtype=dtype, keepdims=keepdims, initial=initial)

def prod(a, axis=None, dtype=None, out=None, keepdims=False):
    a = asarray(a)
    return a.prod(axis=axis, dtype=dtype, keepdims=keepdims)

def nansum(a, axis=None, dtype=None, out=None, keepdims=False):
    a = asarray(a)
    clean = ndarray([0 if (isinstance(v, float) and math.isnan(v)) else v
                     for v in a._data], dtype=a.dtype, shape=a._shape)
    return clean.sum(axis=axis, keepdims=keepdims)

def nanprod(a, axis=None, dtype=None, out=None, keepdims=False):
    a = asarray(a)
    clean = ndarray([1 if (isinstance(v, float) and math.isnan(v)) else v
                     for v in a._data], dtype=a.dtype, shape=a._shape)
    return clean.prod(axis=axis, keepdims=keepdims)

def mean(a, axis=None, dtype=None, out=None, keepdims=False):
    return asarray(a).mean(axis=axis, keepdims=keepdims)

def nanmean(a, axis=None, dtype=None, out=None, keepdims=False):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))],
                    dtype=a.dtype)
    return clean.mean()

def std(a, axis=None, dtype=None, out=None, ddof=0, keepdims=False):
    return asarray(a).std(axis=axis, ddof=ddof, keepdims=keepdims)

def nanstd(a, axis=None, ddof=0, keepdims=False):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))], dtype=a.dtype)
    return clean.std(ddof=ddof)

def var(a, axis=None, dtype=None, out=None, ddof=0, keepdims=False):
    return asarray(a).var(axis=axis, ddof=ddof, keepdims=keepdims)

def nanvar(a, axis=None, ddof=0, keepdims=False):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))], dtype=a.dtype)
    return clean.var(ddof=ddof)

def min(a, axis=None, out=None, keepdims=False, initial=None):
    return asarray(a).min(axis=axis, keepdims=keepdims)

def max(a, axis=None, out=None, keepdims=False, initial=None):
    return asarray(a).max(axis=axis, keepdims=keepdims)

def nanmin(a, axis=None, out=None, keepdims=False):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))], dtype=a.dtype)
    return clean.min()

def nanmax(a, axis=None, out=None, keepdims=False):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))], dtype=a.dtype)
    return clean.max()

def ptp(a, axis=None, out=None, keepdims=False):
    return asarray(a).ptp(axis=axis)

def cumsum(a, axis=None, dtype=None, out=None):
    return asarray(a).cumsum(axis=axis)

def cumprod(a, axis=None, dtype=None, out=None):
    return asarray(a).cumprod(axis=axis)

def nancumsum(a, axis=None, dtype=None, out=None):
    a = asarray(a)
    clean = [0 if (isinstance(v, float) and math.isnan(v)) else v for v in a._data]
    return ndarray(clean, dtype=a.dtype).cumsum()

def nancumprod(a, axis=None, dtype=None, out=None):
    a = asarray(a)
    clean = [1 if (isinstance(v, float) and math.isnan(v)) else v for v in a._data]
    return ndarray(clean, dtype=a.dtype).cumprod()

def diff(a, n=1, axis=-1, prepend=None, append=None):
    a = asarray(a)
    data = list(a._data)
    for _ in range(n):
        data = [data[i+1] - data[i] for i in range(len(data)-1)]
    return ndarray(data, dtype=_dtype_cls('float64'))

def gradient(f, *varargs, axis=None, edge_order=1):
    f = asarray(f)
    spacing = varargs[0] if varargs else 1.0
    data = f._data
    n = len(data)
    out = [0.0] * n
    if n == 1:
        return ndarray([0.0])
    out[0] = (data[1] - data[0]) / spacing
    out[-1] = (data[-1] - data[-2]) / spacing
    for i in range(1, n-1):
        out[i] = (data[i+1] - data[i-1]) / (2 * spacing)
    return ndarray(out, dtype=_dtype_cls('float64'))

def ediff1d(ary, to_end=None, to_begin=None):
    ary = asarray(ary).ravel()
    d = [ary._data[i+1] - ary._data[i] for i in range(len(ary._data)-1)]
    if to_begin is not None:
        d = list(asarray(to_begin)._data) + d
    if to_end is not None:
        d = d + list(asarray(to_end)._data)
    return ndarray(d, dtype=_dtype_cls('float64'))

def cross(a, b, axisa=-1, axisb=-1, axisc=-1, axis=None):
    a, b = asarray(a), asarray(b)
    if len(a._data) == 3 and len(b._data) == 3:
        ax, ay, az = a._data
        bx, by, bz = b._data
        return ndarray([ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx],
                       dtype=_dtype_cls('float64'))
    if len(a._data) == 2 and len(b._data) == 2:
        return a._data[0]*b._data[1] - a._data[1]*b._data[0]
    raise ValueError("cross product requires 2D or 3D vectors")

def dot(a, b):
    from .array import matmul
    return matmul(asarray(a), asarray(b))

def vdot(a, b):
    a, b = asarray(a).ravel(), asarray(b).ravel()
    return builtins_sum(x.conjugate()*y if isinstance(x, complex) else x*y
                         for x, y in zip(a._data, b._data))

def inner(a, b):
    from .array import matmul
    return matmul(asarray(a), asarray(b))

def outer(a, b):
    a, b = asarray(a).ravel(), asarray(b).ravel()
    out = [x * y for x in a._data for y in b._data]
    return ndarray(out, dtype=_dtype_cls('float64'), shape=(len(a._data), len(b._data)))

def kron(a, b):
    a, b = asarray(a), asarray(b)
    out = []
    for va in a._data:
        for vb in b._data:
            out.append(va * vb)
    return ndarray(out, dtype=_dtype_cls('float64'))

def tensordot(a, b, axes=2):
    # simplified: only full contraction
    a, b = asarray(a), asarray(b)
    from .array import matmul
    return matmul(a, b)

def einsum(subscripts, *operands, **kwargs):
    # Minimal support: ij,jk->ik  (matrix multiply)
    operands = [asarray(o) for o in operands]
    if subscripts.replace(' ', '') in ('ij,jk->ik', 'ij,jk->ki'):
        return dot(operands[0], operands[1])
    if subscripts.replace(' ', '') in ('i,i->', 'i,i'):
        return vdot(operands[0], operands[1])
    raise NotImplementedError(f"einsum subscript '{subscripts}' not yet supported in pure mode")

# shadow builtins.sum
import builtins as _builtins
builtins_sum = _builtins.sum


# ── stats / special ───────────────────────────────────────────────────────────
def median(a, axis=None, out=None, overwrite_input=False, keepdims=False):
    a = asarray(a)
    data = sorted(a._data)
    n = len(data)
    if n % 2 == 1:
        return data[n // 2]
    return (data[n//2 - 1] + data[n//2]) / 2.0

def nanmedian(a, axis=None, out=None, overwrite_input=False, keepdims=False):
    a = asarray(a)
    data = sorted(v for v in a._data if not (isinstance(v, float) and math.isnan(v)))
    n = len(data)
    if n == 0:
        return float('nan')
    if n % 2 == 1:
        return data[n // 2]
    return (data[n//2 - 1] + data[n//2]) / 2.0

def percentile(a, q, axis=None, out=None, interpolation='linear', keepdims=False):
    a = asarray(a)
    data = sorted(a._data)
    n = len(data)
    idx = (q / 100.0) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    frac = idx - lo
    return data[lo] + frac * (data[hi] - data[lo])

def nanpercentile(a, q, axis=None, **kwargs):
    a = asarray(a)
    clean = ndarray([v for v in a._data if not (isinstance(v, float) and math.isnan(v))], dtype=a.dtype)
    return percentile(clean, q)

def quantile(a, q, axis=None, **kwargs):
    return percentile(a, q * 100, axis=axis)

def nanquantile(a, q, axis=None, **kwargs):
    return nanpercentile(a, q * 100, axis=axis)

def average(a, axis=None, weights=None, returned=False):
    a = asarray(a)
    if weights is None:
        avg = mean(a, axis=axis)
        return (avg, float(a.size)) if returned else avg
    w = asarray(weights)
    wsum = _builtins.sum(w._data)
    avg = _builtins.sum(v * wv for v, wv in zip(a._data, w._data)) / wsum
    return (avg, wsum) if returned else avg

def correlate(a, v, mode='valid'):
    a, v = asarray(a), asarray(v)
    na, nv = len(a._data), len(v._data)
    if mode == 'full':
        out_len = na + nv - 1
    elif mode == 'same':
        out_len = max(na, nv)
    else:  # valid
        out_len = max(na, nv) - min(na, nv) + 1
    out = []
    for k in range(out_len):
        s = 0.0
        for i in range(nv):
            j = k - (nv - 1) + i if mode != 'full' else k - i
            if 0 <= j < na:
                s += a._data[j] * v._data[i]
        out.append(s)
    return ndarray(out, dtype=_dtype_cls('float64'))

def convolve(a, v, mode='full'):
    return correlate(a, ndarray(list(reversed(v._data if isinstance(v, ndarray) else list(v))),
                                dtype=_dtype_cls('float64')), mode=mode)

def cov(m, y=None, rowvar=True, bias=False, ddof=None, fweights=None, aweights=None):
    m = asarray(m)
    if m.ndim == 1:
        m = m.reshape(1, -1)
    if y is not None:
        y = asarray(y)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        m = ndarray(m._data + y._data, dtype=m.dtype,
                    shape=(m._shape[0] + y._shape[0], m._shape[1]))
    if not rowvar:
        m = m.transpose()
    n_vars, n_obs = m._shape
    if ddof is None:
        ddof = 0 if bias else 1
    means = [_builtins.sum(m._data[r*n_obs:(r+1)*n_obs]) / n_obs for r in range(n_vars)]
    result = []
    for i in range(n_vars):
        row_i = m._data[i*n_obs:(i+1)*n_obs]
        for j in range(n_vars):
            row_j = m._data[j*n_obs:(j+1)*n_obs]
            cov_ij = _builtins.sum((a - means[i]) * (b - means[j])
                                    for a, b in zip(row_i, row_j)) / (n_obs - ddof)
            result.append(cov_ij)
    return ndarray(result, dtype=_dtype_cls('float64'), shape=(n_vars, n_vars))

def corrcoef(x, y=None, rowvar=True):
    c = cov(x, y, rowvar=rowvar)
    if isinstance(c, ndarray) and c.ndim == 2:
        n = c._shape[0]
        diag_sqrt = [math.sqrt(c._data[i*n+i]) for i in range(n)]
        result = []
        for i in range(n):
            for j in range(n):
                denom = diag_sqrt[i] * diag_sqrt[j]
                result.append(c._data[i*n+j] / denom if denom != 0 else 0.0)
        return ndarray(result, dtype=_dtype_cls('float64'), shape=(n, n))
    return c

def histogram(a, bins=10, range=None, density=False, weights=None):
    a = asarray(a)
    data = a._data
    if range is None:
        lo, hi = _builtins.min(data), _builtins.max(data)
    else:
        lo, hi = range
    if isinstance(bins, int):
        n_bins = bins
        edges = [lo + (hi - lo) * i / n_bins for i in range(n_bins + 1)]
    else:
        edges = list(asarray(bins)._data)
        n_bins = len(edges) - 1
    counts = [0] * n_bins
    for v in data:
        for i in range(n_bins):
            if edges[i] <= v < edges[i+1] or (i == n_bins-1 and v == edges[-1]):
                counts[i] += 1
                break
    return ndarray(counts, dtype=_dtype_cls('int64')), ndarray(edges, dtype=_dtype_cls('float64'))

def histogram2d(x, y, bins=10, range=None, density=False, weights=None):
    x, y = asarray(x), asarray(y)
    # simplified: equal bin count for both axes
    _, xedges = histogram(x, bins=bins if isinstance(bins, int) else bins[0])
    _, yedges = histogram(y, bins=bins if isinstance(bins, int) else bins[1])
    nx = len(xedges._data) - 1
    ny = len(yedges._data) - 1
    counts = [0] * (nx * ny)
    xe, ye = xedges._data, yedges._data
    for vx, vy in zip(x._data, y._data):
        xi = next((i for i in range(nx) if xe[i] <= vx < xe[i+1]), nx-1 if vx == xe[-1] else None)
        yi = next((i for i in range(ny) if ye[i] <= vy < ye[i+1]), ny-1 if vy == ye[-1] else None)
        if xi is not None and yi is not None:
            counts[xi * ny + yi] += 1
    return ndarray(counts, dtype=_dtype_cls('int64'), shape=(nx, ny)), xedges, yedges

def histogramdd(sample, bins=10, range=None, density=False, weights=None):
    raise NotImplementedError("histogramdd not yet supported in pure mode")

def bincount(x, weights=None, minlength=0):
    x = asarray(x)
    n = _builtins.max(_builtins.max(x._data) + 1, minlength)
    counts = [0.0] * n
    for i, v in enumerate(x._data):
        w = weights._data[i] if weights is not None else 1
        counts[int(v)] += w
    return ndarray(counts, dtype=_dtype_cls('float64' if weights else 'int64'))

def digitize(x, bins, right=False):
    x = asarray(x)
    bins = list(asarray(bins)._data)
    out = []
    for v in x._data:
        idx = _builtins.sum(1 for b in bins if (b <= v if not right else b < v))
        out.append(idx)
    return ndarray(out, dtype=_dtype_cls('int64'))

def interp(x, xp, fp, left=None, right=None, period=None):
    x = asarray(x)
    xp = list(asarray(xp)._data)
    fp = list(asarray(fp)._data)
    out = []
    for xi in x._data:
        if xi <= xp[0]:
            out.append(fp[0] if left is None else left)
        elif xi >= xp[-1]:
            out.append(fp[-1] if right is None else right)
        else:
            for i in range(len(xp)-1):
                if xp[i] <= xi <= xp[i+1]:
                    t = (xi - xp[i]) / (xp[i+1] - xp[i])
                    out.append(fp[i] + t * (fp[i+1] - fp[i]))
                    break
    return ndarray(out, dtype=_dtype_cls('float64'), shape=x._shape)

def trapz(y, x=None, dx=1.0, axis=-1):
    y = asarray(y)
    data = y._data
    n = len(data)
    if x is None:
        return _builtins.sum((data[i] + data[i+1]) / 2 * dx for i in range(n-1))
    x = asarray(x)
    return _builtins.sum((data[i] + data[i+1]) / 2 * (x._data[i+1] - x._data[i])
                          for i in range(n-1))

def i0(x):
    """Modified Bessel function of the first kind, order 0 (approximation)."""
    x = asarray(x)
    def _i0_scalar(t):
        t = abs(t)
        s, term, k = 1.0, 1.0, 1
        while True:
            term *= (t / (2 * k)) ** 2
            s += term
            if term < 1e-15:
                break
            k += 1
        return s
    return ndarray([_i0_scalar(v) for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)

def sinc(x):
    x = asarray(x)
    def _sinc(v):
        if v == 0:
            return 1.0
        pv = math.pi * v
        return math.sin(pv) / pv
    return ndarray([_sinc(v) for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)

def lcm(a, b):
    return _ufunc2(math.lcm)(a, b)

def gcd(a, b):
    return _ufunc2(math.gcd)(a, b)

def modf(x):
    x = asarray(x)
    int_parts  = ndarray([math.trunc(v) for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)
    frac_parts = ndarray([math.modf(v)[0] for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)
    return frac_parts, int_parts

def frexp(x):
    x = asarray(x)
    mantissas = ndarray([math.frexp(v)[0] for v in x._data], dtype=_dtype_cls('float64'), shape=x._shape)
    exponents = ndarray([math.frexp(v)[1] for v in x._data], dtype=_dtype_cls('int64'),   shape=x._shape)
    return mantissas, exponents

def ldexp(x1, x2):
    x1 = asarray(x1)
    x2 = asarray(x2) if isinstance(x2, ndarray) else [x2] * x1.size
    x2_data = x2._data if isinstance(x2, ndarray) else x2
    return ndarray([math.ldexp(v, e) for v, e in zip(x1._data, x2_data)],
                   dtype=_dtype_cls('float64'), shape=x1._shape)

def spacing(x):
    """ULP spacing (smallest representable difference)."""
    import sys
    return ndarray([sys.float_info.epsilon * abs(v) if v != 0 else sys.float_info.min
                    for v in asarray(x)._data], dtype=_dtype_cls('float64'))

def nextafter(x1, x2):
    import struct
    def _next(a, b):
        if math.isnan(a) or math.isnan(b):
            return float('nan')
        if a == b:
            return a
        packed = struct.pack('d', a)
        n = struct.unpack('Q', packed)[0]
        n += 1 if b > a else -1
        return struct.unpack('d', struct.pack('Q', n))[0]
    return _ufunc2(_next)(x1, x2)
