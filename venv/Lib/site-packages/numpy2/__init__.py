"""
numpy2 - Drop-in NumPy replacement, pure Python, no NumPy required
====================================================================

Replace every ``import numpy as np`` with ``import numpy2 as np`` and
everything works identically — PLUS built-in JSON serialization and
web framework integration.

    >>> import numpy2 as np          # replaces: import numpy as np
    >>> arr = np.array([1, 2, 3])    # identical API
    >>> arr.mean()                    # 2.0
    >>> np.to_json(arr)              # '[1, 2, 3]'

NumPy is used as an optional accelerator when installed; if it is absent
every operation runs in pure Python.
"""

__version__ = "2.4.4"
__author__  = "Mahesh Makvana"
__email__   = "maheshmakwana527@gmail.com"
__license__ = "MIT"

# ── 1. dtype system ───────────────────────────────────────────────────────────
from .dtypes import (
    dtype,
    bool_, bool8,
    int8, int16, int32, int64,
    int_, intp, intc,
    uint8, uint16, uint32, uint64,
    float16, float32, float64,
    float_, double, single, half,
    complex64, complex128,
    object_, str_, bytes_,
    longdouble, clongdouble,
    result_type,
)
# extra aliases
bool8     = bool_
csingle   = complex64
cdouble   = complex128
longfloat = longdouble

# ── 2. ndarray & array creation ───────────────────────────────────────────────
from .array import (
    ndarray,
    array, asarray, ascontiguousarray, asfortranarray,
    zeros, ones, full, empty,
    zeros_like, ones_like, full_like, empty_like,
    eye, identity,
    arange, linspace, logspace, geomspace,
    diag, diagflat, tril, triu, vander,
    meshgrid,
    indices, fromiter, frombuffer, fromfunction, fromstring,
    loadtxt, savetxt, load, save, savez,
    concatenate, stack, vstack, hstack, dstack, column_stack, row_stack,
    split, hsplit, vsplit, dsplit,
    tile, repeat, unique,
    flip, fliplr, flipud, rot90, roll, pad,
    broadcast_to, broadcast_arrays,
    expand_dims, squeeze,
    atleast_1d, atleast_2d, atleast_3d,
    where, select, argwhere,
    argmax, argmin, argsort, sort, lexsort, searchsorted,
    count_nonzero, flatnonzero, nonzero,
    isnan, isinf, isfinite, isneginf, isposinf,
    isreal, iscomplex, isscalar, isclose, allclose,
    array_equal, array_equiv,
    may_share_memory, shares_memory,
    can_cast, common_type, min_scalar_type, promote_types,
    shape, ndim, size,
    copyto, iterable,
    unravel_index, ravel_multi_index,
    ix_, ndindex, ndenumerate,
    apply_along_axis, apply_over_axes,
    vectorize, frompyfunc,
    # constants
    nan, inf, pi, e, newaxis,
    # matrix ops
    matmul,
    # broadcast helper (internal but useful)
    _broadcast_shapes as _broadcast_shapes_internal,
)
PINF = inf
NINF = -inf
Inf  = inf
Infinity = inf
NaN  = nan
False_ = False
True_  = True
PZERO  = 0.0
NZERO  = -0.0

# mgrid / ogrid stubs
class _MGridClass:
    def __getitem__(self, key):
        raise NotImplementedError("Use meshgrid or arange in numpy2 pure mode")
mgrid = _MGridClass()
ogrid = _MGridClass()

# index_exp / s_ stubs
class _IndexExpClass:
    def __getitem__(self, key):
        return key
index_exp = _IndexExpClass()
s_        = _IndexExpClass()

c_ = None  # not yet implemented
r_ = None

# ── 3. math / ufuncs ──────────────────────────────────────────────────────────
from .math_ops import (
    # trig
    sin, cos, tan,
    arcsin, arccos, arctan, arctan2,
    hypot, deg2rad, rad2deg, degrees, radians, unwrap,
    # hyperbolic
    sinh, cosh, tanh, arcsinh, arccosh, arctanh,
    # exp / log
    exp, exp2, expm1, log, log2, log10, log1p,
    # rounding
    floor, ceil, trunc, rint, fix, around, round_,
    # arithmetic ufuncs
    add, subtract, multiply, divide, true_divide, floor_divide,
    negative, positive, power, float_power,
    remainder, mod, fmod,
    absolute, fabs, sign, heaviside,
    sqrt, cbrt, square, reciprocal,
    # logical
    logical_and, logical_or, logical_xor, logical_not,
    # bitwise
    bitwise_and, bitwise_or, bitwise_xor, bitwise_not, invert,
    left_shift, right_shift,
    # comparison
    greater, greater_equal, less, less_equal, equal, not_equal,
    maximum, minimum, fmax, fmin,
    # complex
    real, imag, conj, conjugate, angle,
    # reductions
    sum, prod, nansum, nanprod,
    mean, nanmean, std, nanstd, var, nanvar,
    min, max, nanmin, nanmax,
    ptp, cumsum, cumprod, nancumsum, nancumprod,
    diff, gradient, ediff1d,
    # linear algebra
    cross, dot, vdot, inner, outer, kron, tensordot, einsum,
    # stats
    median, nanmedian,
    percentile, nanpercentile, quantile, nanquantile,
    average, correlate, convolve,
    cov, corrcoef,
    histogram, histogram2d, histogramdd,
    bincount, digitize, interp, trapz,
    i0, sinc,
    lcm, gcd, modf, frexp, ldexp, spacing, nextafter,
    # abs alias
    abs as absolute_fn,
)
# shadow Python builtins with numpy2 versions
abs   = absolute
round = around

# ── 4. submodules ─────────────────────────────────────────────────────────────
from . import linalg
from . import fft
from . import random
from . import compat

# make polynomial, ma, lib stubs (users can still use them via numpy if installed)
try:
    import numpy as _np_opt
    polynomial = _np_opt.polynomial
    ma         = _np_opt.ma
    lib        = _np_opt.lib
    char       = _np_opt.char
    try:
        strings = _np_opt.strings
    except AttributeError:
        pass
    try:
        exceptions = _np_opt.exceptions
    except AttributeError:
        pass
    # also expose numpy's testing module
    testing = _np_opt.testing
except ImportError:
    # provide minimal stubs so imports don't crash
    class _Stub:
        def __getattr__(self, name):
            raise ImportError(f"numpy2: 'numpy.{name}' requires NumPy to be installed")
    polynomial = _Stub()
    ma         = _Stub()
    lib        = _Stub()
    char       = _Stub()
    testing    = _Stub()

# ── 5. numpy2 advanced features ──────────────────────────────────────────────
from .advanced import (
    ArrayCache,
    ArrayPipeline,
    ArrayValidator,
    ArrayValidationError,
    ProfiledArray,
    compress_array,
    decompress_array,
    compress_to_b64,
    decompress_from_b64,
    sliding_window_view,
    batch_apply,
    to_structured,
    array_chunks,
    describe,
    # ── New in 2.4.0 ──────────────────────────────────────────────────────────
    NamedArray,
    vmapped, vmap,
    scan,
    smart_axis, resolve_axis,
    nan_safe_convert, NaNInfEncoder, nan_safe_json_dumps,
    ThreadSafeArray,
    CompatLayer,
    auto_type_convert,
    chunked_reduce,
    broadcast_explicit, align_shapes,
    einsum_enhanced,
    array_memory_usage,
    LazyArray,
)

# ── 6. numpy2 web extras ──────────────────────────────────────────────────────
from .core import (
    to_json, from_json,
    serialize, deserialize,
    JSONEncoder, JSONDecoder,
)

from .converters import (
    numpy_to_python, pandas_to_json,
    python_to_numpy, infer_dtype,
    safe_cast, batch_convert,
)

from .integrations import (
    FastAPIResponse, FlaskResponse, DjangoResponse,
    setup_json_encoder, create_response_handler,
)

# ── 6. nditer / ndenumerate compatibility ────────────────────────────────────
class nditer:
    """Minimal nditer stub."""
    def __init__(self, op, flags=None, op_flags=None, op_dtypes=None,
                 order='K', casting='safe', op_axes=None, itershape=None,
                 buffersize=0):
        from .array import asarray
        self._arr = asarray(op) if not isinstance(op, (list, tuple)) else [asarray(o) for o in op]
        self._idx = 0
        if isinstance(self._arr, list):
            self._data = list(zip(*[a._data for a in self._arr]))
        else:
            self._data = self._arr._data

    def __iter__(self):
        return self

    def __next__(self):
        if self._idx >= len(self._data):
            raise StopIteration
        val = self._data[self._idx]
        self._idx += 1
        return val

    def __len__(self):
        return len(self._data)

    @property
    def finished(self):
        return self._idx >= len(self._data)

    def iternext(self):
        if self._idx < len(self._data):
            self._idx += 1
            return True
        return False

# ── 7. poly functions ─────────────────────────────────────────────────────────
from .math_ops import interp as _interp

def polyval(p, x):
    """Evaluate polynomial with coefficients p at points x."""
    from .array import asarray
    p = asarray(p)
    x = asarray(x)
    result = zeros_like(x, dtype='float64')
    for coef in p._data:
        result = result * x + coef
    return result

def polyfit(x, y, deg):
    """Least-squares polynomial fit. Returns coefficients."""
    from .array import asarray
    from .linalg import lstsq
    x = asarray(x, dtype='float64')
    y = asarray(y, dtype='float64')
    # Vandermonde matrix
    V = vander(x, deg + 1)
    coeffs, _, _, _ = lstsq(V, y)
    return coeffs

def polyadd(a1, a2):
    from .array import asarray
    a1, a2 = asarray(a1, dtype='float64'), asarray(a2, dtype='float64')
    n1, n2 = len(a1._data), len(a2._data)
    if n1 < n2:
        a1 = concatenate([zeros(n2 - n1, dtype='float64'), a1])
    elif n2 < n1:
        a2 = concatenate([zeros(n1 - n2, dtype='float64'), a2])
    return a1 + a2

def polysub(a1, a2):
    return polyadd(a1, -asarray(a2, dtype='float64'))

def polymul(a1, a2):
    return convolve(a1, a2)

def polydiv(u, v):
    u = list(asarray(u, dtype='float64')._data)
    v = list(asarray(v, dtype='float64')._data)
    # polynomial long division
    q, r = [], list(u)
    while len(r) >= len(v):
        coef = r[0] / v[0]
        q.append(coef)
        for i in range(len(v)):
            r[i] -= coef * v[i]
        r.pop(0)
    return array(q, dtype='float64'), array(r, dtype='float64')

def polyder(p, m=1):
    p = list(asarray(p, dtype='float64')._data)
    for _ in range(m):
        n = len(p) - 1
        p = [(n - i) * p[i] for i in range(n)]
    return array(p, dtype='float64')

def polyint(p, m=1, k=None):
    p = list(asarray(p, dtype='float64')._data)
    for _ in range(m):
        n = len(p)
        p = [p[i] / (n - i) for i in range(n)] + [0.0]
    return array(p, dtype='float64')

def poly(seq_of_zeros):
    """Return polynomial with given roots."""
    seq = asarray(seq_of_zeros, dtype='float64')
    result = array([1.0])
    for root in seq._data:
        result = polymul(result, array([1.0, -root]))
    return result

class poly1d:
    """1-D polynomial class."""
    def __init__(self, c_or_r, r=False, variable=None):
        c = asarray(c_or_r, dtype='float64')
        if r:
            self.coeffs = poly(c)
        else:
            self.coeffs = c

    def __call__(self, val):
        return polyval(self.coeffs, asarray(val, dtype='float64'))

    @property
    def order(self):
        return len(self.coeffs._data) - 1

    def __repr__(self):
        return f"poly1d({self.coeffs.tolist()})"


# ── 8. seterr / errstate (stubs) ──────────────────────────────────────────────
_err_state = {'divide': 'warn', 'over': 'warn', 'under': 'ignore', 'invalid': 'warn'}

def seterr(divide=None, over=None, under=None, invalid=None, all=None):
    old = dict(_err_state)
    for key, val in [('divide', divide), ('over', over), ('under', under), ('invalid', invalid)]:
        if val is not None:
            _err_state[key] = val
    if all is not None:
        for key in _err_state:
            _err_state[key] = all
    return old

def geterr():
    return dict(_err_state)

class errstate:
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._old = {}
    def __enter__(self):
        self._old = seterr(**self._kwargs)
    def __exit__(self, *args):
        seterr(**self._old)

def seterrcall(func):
    pass

def geterrcall():
    return None


# ── 9. __all__ ────────────────────────────────────────────────────────────────
__all__ = [
    # dtype
    'dtype',
    'bool_', 'bool8', 'int8', 'int16', 'int32', 'int64',
    'int_', 'intp', 'intc',
    'uint8', 'uint16', 'uint32', 'uint64',
    'float16', 'float32', 'float64', 'float_', 'double', 'single', 'half',
    'complex64', 'complex128', 'csingle', 'cdouble',
    'object_', 'str_', 'bytes_',
    'longdouble', 'longfloat', 'clongdouble',
    'result_type',
    # ndarray & creation
    'ndarray', 'matrix',
    'array', 'asarray', 'ascontiguousarray', 'asfortranarray',
    'zeros', 'ones', 'full', 'empty',
    'zeros_like', 'ones_like', 'full_like', 'empty_like',
    'eye', 'identity', 'arange', 'linspace', 'logspace', 'geomspace',
    'diag', 'diagflat', 'tril', 'triu', 'vander',
    'meshgrid', 'mgrid', 'ogrid', 'indices',
    'fromiter', 'frombuffer', 'fromfunction', 'fromstring',
    'loadtxt', 'savetxt', 'load', 'save', 'savez',
    'concatenate', 'stack', 'vstack', 'hstack', 'dstack', 'column_stack', 'row_stack',
    'split', 'hsplit', 'vsplit', 'dsplit',
    'tile', 'repeat', 'unique',
    'flip', 'fliplr', 'flipud', 'rot90', 'roll', 'pad',
    'broadcast_to', 'broadcast_arrays', 'expand_dims', 'squeeze',
    'atleast_1d', 'atleast_2d', 'atleast_3d',
    'where', 'select', 'argwhere', 'argmax', 'argmin', 'argsort', 'sort', 'lexsort',
    'searchsorted', 'count_nonzero', 'flatnonzero', 'nonzero',
    'isnan', 'isinf', 'isfinite', 'isneginf', 'isposinf',
    'isreal', 'iscomplex', 'isscalar', 'isclose', 'allclose',
    'array_equal', 'array_equiv',
    'may_share_memory', 'shares_memory',
    'can_cast', 'common_type', 'min_scalar_type', 'promote_types',
    'shape', 'ndim', 'size', 'copyto', 'iterable',
    'unravel_index', 'ravel_multi_index', 'ix_', 'ndindex', 'ndenumerate',
    'apply_along_axis', 'apply_over_axes', 'vectorize', 'frompyfunc',
    'nan', 'inf', 'pi', 'e', 'newaxis', 'nan', 'inf',
    'NaN', 'Inf', 'Infinity', 'PINF', 'NINF',
    'matmul', 'nditer', 'index_exp', 's_',
    # math
    'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'arctan2',
    'hypot', 'deg2rad', 'rad2deg', 'degrees', 'radians', 'unwrap',
    'sinh', 'cosh', 'tanh', 'arcsinh', 'arccosh', 'arctanh',
    'exp', 'exp2', 'expm1', 'log', 'log2', 'log10', 'log1p',
    'floor', 'ceil', 'trunc', 'rint', 'fix', 'around', 'round_',
    'add', 'subtract', 'multiply', 'divide', 'true_divide', 'floor_divide',
    'negative', 'positive', 'power', 'float_power',
    'remainder', 'mod', 'fmod',
    'absolute', 'fabs', 'sign', 'heaviside',
    'sqrt', 'cbrt', 'square', 'reciprocal',
    'logical_and', 'logical_or', 'logical_xor', 'logical_not',
    'bitwise_and', 'bitwise_or', 'bitwise_xor', 'bitwise_not', 'invert',
    'left_shift', 'right_shift',
    'greater', 'greater_equal', 'less', 'less_equal', 'equal', 'not_equal',
    'maximum', 'minimum', 'fmax', 'fmin',
    'real', 'imag', 'conj', 'conjugate', 'angle',
    'sum', 'prod', 'nansum', 'nanprod',
    'mean', 'nanmean', 'std', 'nanstd', 'var', 'nanvar',
    'min', 'max', 'nanmin', 'nanmax',
    'ptp', 'cumsum', 'cumprod', 'nancumsum', 'nancumprod',
    'diff', 'gradient', 'ediff1d',
    'cross', 'dot', 'vdot', 'inner', 'outer', 'kron', 'tensordot', 'einsum',
    'median', 'nanmedian', 'percentile', 'nanpercentile', 'quantile', 'nanquantile',
    'average', 'correlate', 'convolve', 'cov', 'corrcoef',
    'histogram', 'histogram2d', 'histogramdd',
    'bincount', 'digitize', 'interp', 'trapz',
    'i0', 'sinc', 'lcm', 'gcd', 'modf', 'frexp', 'ldexp', 'spacing', 'nextafter',
    # poly
    'polyval', 'polyfit', 'polyadd', 'polysub', 'polymul', 'polydiv',
    'polyder', 'polyint', 'poly', 'poly1d',
    # err state
    'seterr', 'geterr', 'errstate', 'seterrcall', 'geterrcall',
    # submodules
    'linalg', 'fft', 'random', 'compat', 'polynomial', 'ma', 'lib', 'testing', 'char',
    # web extras
    'to_json', 'from_json', 'serialize', 'deserialize',
    'JSONEncoder', 'JSONDecoder',
    'numpy_to_python', 'pandas_to_json', 'python_to_numpy',
    'infer_dtype', 'safe_cast', 'batch_convert',
    'FastAPIResponse', 'FlaskResponse', 'DjangoResponse',
    'setup_json_encoder', 'create_response_handler',
    # advanced
    'ArrayCache', 'ArrayPipeline', 'ArrayValidator', 'ArrayValidationError',
    'ProfiledArray',
    'compress_array', 'decompress_array', 'compress_to_b64', 'decompress_from_b64',
    'sliding_window_view', 'batch_apply', 'to_structured',
    'array_chunks', 'describe',
    # New in 2.4.0
    'NamedArray',
    'vmapped', 'vmap',
    'scan',
    'smart_axis', 'resolve_axis',
    'nan_safe_convert', 'NaNInfEncoder', 'nan_safe_json_dumps',
    'ThreadSafeArray',
    'CompatLayer',
    'auto_type_convert',
    'chunked_reduce',
    'broadcast_explicit', 'align_shapes',
    'einsum_enhanced',
    'array_memory_usage',
    'LazyArray',
]

# matrix alias (2-D array subclass stub)
matrix = ndarray
