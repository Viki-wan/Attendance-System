"""
numpy2.array - Pure-Python ndarray implementation

A flat list backed n-dimensional array that mirrors the NumPy ndarray API.
NumPy is used as an optional accelerator when installed; when absent every
operation is executed in pure Python.
"""

import math
import operator
import copy
import itertools
from typing import Any, List, Optional, Tuple, Union

from .dtypes import dtype as _dtype_cls, _normalise, _infer_dtype_from_data

# ── optional NumPy accelerator ────────────────────────────────────────────────
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _np = None
    _HAS_NUMPY = False

# ── helpers ───────────────────────────────────────────────────────────────────

def _prod(iterable):
    r = 1
    for x in iterable:
        r *= x
    return r

def _flatten(data):
    """Recursively flatten a nested list/tuple to a 1-D list."""
    if isinstance(data, (list, tuple)):
        out = []
        for item in data:
            out.extend(_flatten(item))
        return out
    return [data]

def _shape_of(data):
    """Infer shape tuple from nested list/tuple."""
    if not isinstance(data, (list, tuple)):
        return ()
    if len(data) == 0:
        return (0,)
    inner = _shape_of(data[0])
    return (len(data),) + inner

def _strides_for(shape, itemsize=8):
    """C-contiguous strides (bytes per step along each axis)."""
    if not shape:
        return ()
    strides = [itemsize]
    for s in reversed(shape[1:]):
        strides.insert(0, strides[0] * s)
    return tuple(strides)

def _broadcast_shapes(*shapes):
    """NumPy broadcast rule: align from right, expand dims of size 1."""
    max_ndim = max(len(s) for s in shapes)
    padded = [(1,) * (max_ndim - len(s)) + tuple(s) for s in shapes]
    result = []
    for dims in zip(*padded):
        non_one = [d for d in dims if d != 1]
        if len(set(non_one)) > 1:
            raise ValueError(f"Cannot broadcast shapes {shapes}")
        result.append(non_one[0] if non_one else 1)
    return tuple(result)

def _indices_for_shape(shape):
    """Yield all multi-index tuples for the given shape (row-major)."""
    return itertools.product(*[range(s) for s in shape])

def _ravel_index(idx, shape):
    """Convert multi-index to flat index (C order)."""
    flat = 0
    for i, (ix, s) in enumerate(zip(idx, shape)):
        flat = flat * s + ix
    return flat

def _unravel_index(flat, shape):
    """Convert flat index to multi-index (C order)."""
    idx = []
    for s in reversed(shape):
        idx.append(flat % s)
        flat //= s
    return tuple(reversed(idx))


# ── NaN / Inf singletons ──────────────────────────────────────────────────────
nan  = float('nan')
inf  = float('inf')
PINF = float('inf')
NINF = float('-inf')
e    = math.e
pi   = math.pi
newaxis = None   # np.newaxis is None


def _is_nan(x):
    try:
        return math.isnan(x)
    except (TypeError, ValueError):
        return False

def _is_inf(x):
    try:
        return math.isinf(x)
    except (TypeError, ValueError):
        return False


# ── ndarray ───────────────────────────────────────────────────────────────────

class ndarray:
    """
    Pure-Python n-dimensional array.

    Internally stores data as a flat Python list.  Shape, dtype, and all
    NumPy-compatible operations are implemented in pure Python.  When NumPy
    is installed the heavy math (linalg, fft) delegates to it automatically.
    """

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(self, data=None, dtype=None, shape=None, order='C'):
        dt = _dtype_cls(dtype)

        if data is None:
            # empty array of given shape
            sz = _prod(shape) if shape else 0
            self._data  = [dt.cast(0)] * sz
            self._shape = tuple(shape) if shape else (0,)
            self._dtype = dt
            return

        # accept another ndarray
        if isinstance(data, ndarray):
            flat = list(data._data)
            inferred_shape = data._shape
        elif _HAS_NUMPY and isinstance(data, _np.ndarray):
            flat = _flatten(data.tolist())
            inferred_shape = data.shape
        elif isinstance(data, (list, tuple)):
            inferred_shape = _shape_of(data)
            flat = _flatten(data)
        elif isinstance(data, range):
            flat = list(data)
            inferred_shape = (len(flat),)
        else:
            # scalar
            flat = [data]
            inferred_shape = ()

        # dtype inference
        if dtype is None:
            dt = _infer_dtype_from_data(flat) if flat else _dtype_cls('float64')
        else:
            dt = _dtype_cls(dtype)

        self._data  = [dt.cast(v) for v in flat]
        self._shape = tuple(shape) if shape else inferred_shape
        self._dtype = dt

    # ── core properties ───────────────────────────────────────────────────────

    @property
    def dtype(self):
        return self._dtype

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, new_shape):
        if _prod(new_shape) != self.size:
            raise ValueError("Cannot reshape: total size must not change")
        self._shape = tuple(new_shape)

    @property
    def ndim(self):
        return len(self._shape)

    @property
    def size(self):
        return _prod(self._shape) if self._shape else 1

    @property
    def itemsize(self):
        return self._dtype.itemsize

    @property
    def nbytes(self):
        return self.size * self.itemsize

    @property
    def strides(self):
        return _strides_for(self._shape, self.itemsize)

    @property
    def T(self):
        return self.transpose()

    @property
    def flat(self):
        return iter(self._data)

    @property
    def real(self):
        return ndarray([v.real if isinstance(v, complex) else v
                        for v in self._data], dtype='float64',
                       shape=self._shape)

    @property
    def imag(self):
        return ndarray([v.imag if isinstance(v, complex) else 0.0
                        for v in self._data], dtype='float64',
                       shape=self._shape)

    # ── list conversion ───────────────────────────────────────────────────────

    def tolist(self):
        if self.ndim == 0:
            return self._data[0] if self._data else None
        def _build(flat_iter, shape):
            if len(shape) == 1:
                return [next(flat_iter) for _ in range(shape[0])]
            return [_build(flat_iter, shape[1:]) for _ in range(shape[0])]
        it = iter(self._data)
        if not self._shape:
            return self._data[0] if self._data else None
        return _build(it, self._shape)

    def tolist_flat(self):
        return list(self._data)

    def tobytes(self):
        import struct as _struct
        fmt = self._dtype._fmt
        if fmt is None:
            return b''
        return _struct.pack(f'{len(self._data)}{fmt}', *self._data)

    # ── indexing & slicing ────────────────────────────────────────────────────

    def _normalise_index(self, key):
        """Convert any index form to a flat integer."""
        if isinstance(key, tuple):
            if len(key) != self.ndim:
                raise IndexError(f"Too many indices: {len(key)} for {self.ndim}-D array")
            idx = []
            for i, (k, s) in enumerate(zip(key, self._shape)):
                if k < 0:
                    k += s
                if not (0 <= k < s):
                    raise IndexError(f"Index {k} out of bounds for axis {i} with size {s}")
                idx.append(k)
            return _ravel_index(idx, self._shape)
        if isinstance(key, int):
            if self.ndim == 1:
                if key < 0:
                    key += self._shape[0]
                return key
            # index first axis
            raise IndexError("Use tuple index for multi-dim arrays")
        raise TypeError(f"Invalid index type: {type(key)}")

    def __getitem__(self, key):
        # boolean mask
        if isinstance(key, ndarray) and key.dtype.kind == 'b':
            return ndarray([v for v, m in zip(self._data, key._data) if m],
                           dtype=self._dtype)

        # integer array fancy indexing
        if isinstance(key, ndarray):
            return ndarray([self._data[i] for i in key._data], dtype=self._dtype)

        # 1-D integer
        if isinstance(key, int):
            if self.ndim == 1:
                k = key if key >= 0 else key + self._shape[0]
                return self._data[k]
            # index first axis → sub-array
            size = _prod(self._shape[1:])
            k = key if key >= 0 else key + self._shape[0]
            start = k * size
            return ndarray(self._data[start:start+size],
                           dtype=self._dtype, shape=self._shape[1:])

        # slice on 1-D
        if isinstance(key, slice) and self.ndim == 1:
            sliced = self._data[key]
            return ndarray(sliced, dtype=self._dtype)

        # tuple of slices/ints
        if isinstance(key, tuple):
            # build new shape and flat data
            if self.ndim == 0:
                return self._data[0]
            # only support all-int tuple (scalar result) for now
            try:
                flat_i = self._normalise_index(key)
                return self._data[flat_i]
            except (IndexError, TypeError):
                pass
            # slice tuple (advanced): simplistic row/col slicing
            return self._slice_tuple(key)

        # numpy array passthrough
        if _HAS_NUMPY and isinstance(key, _np.ndarray):
            return self.__getitem__(ndarray(key.tolist()))

        raise TypeError(f"Unsupported index type: {type(key)}")

    def _slice_tuple(self, key):
        """Handle tuple of ints and slices."""
        # Expand ellipsis
        n_ellipsis = sum(1 for k in key if k is Ellipsis)
        if n_ellipsis > 1:
            raise IndexError("Only one ellipsis allowed")
        if n_ellipsis:
            n_newaxes = sum(1 for k in key if k is None)
            n_fill = self.ndim - (len(key) - n_ellipsis - n_newaxes)
            expanded = []
            for k in key:
                if k is Ellipsis:
                    expanded.extend([slice(None)] * n_fill)
                else:
                    expanded.append(k)
            key = tuple(expanded)

        # Pad with full slices
        key = key + (slice(None),) * (self.ndim - len(key))

        ranges = []
        new_shape_parts = []
        for axis, (k, s) in enumerate(zip(key, self._shape)):
            if isinstance(k, int):
                if k < 0:
                    k += s
                ranges.append([k])
            elif isinstance(k, slice):
                r = range(*k.indices(s))
                ranges.append(r)
                new_shape_parts.append(len(r))
            else:
                raise IndexError(f"Unsupported index element: {k!r}")

        new_data = []
        for multi_idx in itertools.product(*ranges):
            new_data.append(self._data[_ravel_index(multi_idx, self._shape)])

        return ndarray(new_data, dtype=self._dtype,
                       shape=tuple(new_shape_parts) if new_shape_parts else ())

    def __setitem__(self, key, value):
        if isinstance(key, ndarray) and key.dtype.kind == 'b':
            positions = [i for i, m in enumerate(key._data) if m]
            if isinstance(value, ndarray):
                vals = value._data
            elif isinstance(value, (list, tuple)):
                vals = list(value)
            else:
                vals = [value] * len(positions)
            for pos, val in zip(positions, vals):
                self._data[pos] = self._dtype.cast(val)
            return

        if isinstance(key, int) and self.ndim == 1:
            k = key if key >= 0 else key + self._shape[0]
            self._data[k] = self._dtype.cast(value)
            return

        if isinstance(key, tuple):
            flat_i = self._normalise_index(key)
            self._data[flat_i] = self._dtype.cast(value)
            return

        if isinstance(key, slice) and self.ndim == 1:
            indices = range(*key.indices(self._shape[0]))
            if isinstance(value, ndarray):
                vals = value._data
            elif isinstance(value, (list, tuple)):
                vals = list(value)
            else:
                vals = [value] * len(indices)
            for i, v in zip(indices, vals):
                self._data[i] = self._dtype.cast(v)
            return

        raise TypeError(f"Unsupported __setitem__ key: {type(key)}")

    # ── shape manipulation ────────────────────────────────────────────────────

    def reshape(self, *shape, order='C'):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = tuple(shape[0])
        else:
            shape = tuple(shape)
        # handle -1
        if -1 in shape:
            known = _prod(s for s in shape if s != -1)
            shape = tuple(self.size // known if s == -1 else s for s in shape)
        if _prod(shape) != self.size:
            raise ValueError(f"Cannot reshape size {self.size} into {shape}")
        out = ndarray.__new__(ndarray)
        out._data  = list(self._data)
        out._shape = shape
        out._dtype = self._dtype
        return out

    def ravel(self, order='C'):
        return self.reshape(self.size)

    def flatten(self, order='C'):
        return ndarray(list(self._data), dtype=self._dtype)

    def squeeze(self, axis=None):
        if axis is None:
            new_shape = tuple(s for s in self._shape if s != 1)
        else:
            new_shape = tuple(s for i, s in enumerate(self._shape) if i != axis or s != 1)
        return self.reshape(new_shape or (1,))

    def expand_dims(self, axis):
        shape = list(self._shape)
        if axis < 0:
            axis = len(shape) + 1 + axis
        shape.insert(axis, 1)
        return self.reshape(tuple(shape))

    def transpose(self, *axes):
        if self.ndim < 2:
            return ndarray(list(self._data), dtype=self._dtype, shape=self._shape)
        if not axes:
            axes = tuple(reversed(range(self.ndim)))
        elif len(axes) == 1 and isinstance(axes[0], (tuple, list)):
            axes = tuple(axes[0])
        new_shape = tuple(self._shape[a] for a in axes)
        new_data  = [None] * self.size
        for old_idx in _indices_for_shape(self._shape):
            new_idx = tuple(old_idx[a] for a in axes)
            new_data[_ravel_index(new_idx, new_shape)] = \
                self._data[_ravel_index(old_idx, self._shape)]
        out = ndarray.__new__(ndarray)
        out._data  = new_data
        out._shape = new_shape
        out._dtype = self._dtype
        return out

    def swapaxes(self, axis1, axis2):
        axes = list(range(self.ndim))
        axes[axis1], axes[axis2] = axes[axis2], axes[axis1]
        return self.transpose(*axes)

    def astype(self, dt, copy=True):
        dt = _dtype_cls(dt)
        new_data = [dt.cast(v) for v in self._data]
        out = ndarray.__new__(ndarray)
        out._data  = new_data
        out._shape = self._shape
        out._dtype = dt
        return out

    def copy(self, order='C'):
        out = ndarray.__new__(ndarray)
        out._data  = list(self._data)
        out._shape = self._shape
        out._dtype = self._dtype
        return out

    def view(self, dt=None):
        """Shallow view (dtype change not fully supported, returns copy)."""
        if dt is None:
            return self.copy()
        return self.astype(dt)

    def fill(self, value):
        v = self._dtype.cast(value)
        self._data = [v] * self.size

    # ── reductions ────────────────────────────────────────────────────────────

    def _reduce_axis(self, fn, axis, keepdims, initial=None):
        """Generic axis-reduction helper."""
        if axis is None:
            result = self._data[0] if initial is None else initial
            start = 0 if initial is not None else 1
            for v in self._data[start:]:
                result = fn(result, v)
            if keepdims:
                return ndarray([result], shape=(1,)*self.ndim, dtype=self._dtype)
            return result

        if axis < 0:
            axis += self.ndim
        new_shape = tuple(s for i, s in enumerate(self._shape) if i != axis)
        out_size  = _prod(new_shape) if new_shape else 1
        out_data  = [initial] * out_size if initial is not None else [None] * out_size
        counts    = [0] * out_size

        for multi_idx in _indices_for_shape(self._shape):
            reduced_idx = tuple(v for i, v in enumerate(multi_idx) if i != axis)
            flat_out    = _ravel_index(reduced_idx, new_shape) if new_shape else 0
            val         = self._data[_ravel_index(multi_idx, self._shape)]
            if out_data[flat_out] is None:
                out_data[flat_out] = val
            else:
                out_data[flat_out] = fn(out_data[flat_out], val)
            counts[flat_out] += 1

        if keepdims:
            ks = tuple(1 if i == axis else s for i, s in enumerate(self._shape))
            return ndarray(out_data, dtype=self._dtype, shape=ks)
        return ndarray(out_data, dtype=self._dtype,
                       shape=new_shape if new_shape else (1,))

    def sum(self, axis=None, dtype=None, keepdims=False, initial=0):
        out = self._reduce_axis(operator.add, axis, keepdims, initial)
        if dtype is not None and isinstance(out, ndarray):
            return out.astype(dtype)
        return out

    def prod(self, axis=None, dtype=None, keepdims=False):
        out = self._reduce_axis(operator.mul, axis, keepdims, 1)
        if dtype is not None and isinstance(out, ndarray):
            return out.astype(dtype)
        return out

    def min(self, axis=None, keepdims=False):
        return self._reduce_axis(min, axis, keepdims)

    def max(self, axis=None, keepdims=False):
        return self._reduce_axis(max, axis, keepdims)

    def mean(self, axis=None, keepdims=False):
        if axis is None:
            s = sum(self._data)
            m = s / self.size
            if keepdims:
                return ndarray([m], shape=(1,)*self.ndim, dtype=_dtype_cls('float64'))
            return m
        s = self.sum(axis=axis, keepdims=keepdims)
        n = self._shape[axis if axis >= 0 else axis + self.ndim]
        return s / n if isinstance(s, (int, float, complex)) else \
               ndarray([v / n for v in s._data], dtype=_dtype_cls('float64'), shape=s._shape)

    def std(self, axis=None, ddof=0, keepdims=False):
        m = self.mean(axis=axis, keepdims=True)
        if axis is None:
            m_val = m if isinstance(m, (int, float)) else list(m._data)[0]
            sq = [(v - m_val)**2 for v in self._data]
            return math.sqrt(sum(sq) / (self.size - ddof))
        diff = self - m
        return (diff * diff).mean(axis=axis, keepdims=keepdims) ** 0.5

    def var(self, axis=None, ddof=0, keepdims=False):
        v = self.std(axis=axis, ddof=ddof, keepdims=keepdims)
        return v * v if isinstance(v, (int, float)) else \
               ndarray([x*x for x in v._data], dtype=v._dtype, shape=v._shape)

    def cumsum(self, axis=None):
        if axis is None:
            out = []
            acc = 0
            for v in self._data:
                acc += v
                out.append(acc)
            return ndarray(out, dtype=_dtype_cls('float64'))
        raise NotImplementedError("cumsum with axis not yet supported")

    def cumprod(self, axis=None):
        if axis is None:
            out = []
            acc = 1
            for v in self._data:
                acc *= v
                out.append(acc)
            return ndarray(out, dtype=_dtype_cls('float64'))
        raise NotImplementedError("cumprod with axis not yet supported")

    def argmin(self, axis=None):
        if axis is None:
            return self._data.index(min(self._data))
        raise NotImplementedError("argmin with axis not yet supported")

    def argmax(self, axis=None):
        if axis is None:
            return self._data.index(max(self._data))
        raise NotImplementedError("argmax with axis not yet supported")

    def argsort(self, axis=-1, kind='quicksort'):
        if self.ndim == 1 or axis is None:
            indexed = sorted(enumerate(self._data), key=lambda x: x[1])
            return ndarray([i for i, _ in indexed], dtype=_dtype_cls('int64'))
        raise NotImplementedError("argsort with axis not yet supported")

    def sort(self, axis=-1, kind='quicksort'):
        if self.ndim == 1:
            self._data.sort()
            return
        raise NotImplementedError("sort with axis not yet supported")

    def ptp(self, axis=None):
        return self.max(axis=axis) - self.min(axis=axis)

    def clip(self, a_min=None, a_max=None):
        def _clip(v):
            if a_min is not None and v < a_min:
                return a_min
            if a_max is not None and v > a_max:
                return a_max
            return v
        return ndarray([_clip(v) for v in self._data], dtype=self._dtype, shape=self._shape)

    def round(self, decimals=0):
        return ndarray([round(v, decimals) for v in self._data],
                       dtype=self._dtype, shape=self._shape)

    def trace(self, offset=0):
        if self.ndim < 2:
            raise ValueError("trace requires at least 2-D array")
        rows, cols = self._shape[-2], self._shape[-1]
        s = 0
        for i in range(min(rows, cols)):
            r, c = i, i + offset
            if 0 <= r < rows and 0 <= c < cols:
                s += self._data[_ravel_index((r, c), (rows, cols))]
        return s

    def diagonal(self, offset=0):
        if self.ndim < 2:
            raise ValueError("diagonal requires at least 2-D array")
        rows, cols = self._shape[-2], self._shape[-1]
        out = []
        for i in range(min(rows, cols)):
            r, c = i, i + offset
            if 0 <= r < rows and 0 <= c < cols:
                out.append(self._data[_ravel_index((r, c), (rows, cols))])
        return ndarray(out, dtype=self._dtype)

    def any(self, axis=None):
        if axis is None:
            return any(bool(v) for v in self._data)
        return self._reduce_axis(lambda a, b: bool(a) or bool(b), axis, False)

    def all(self, axis=None):
        if axis is None:
            return all(bool(v) for v in self._data)
        return self._reduce_axis(lambda a, b: bool(a) and bool(b), axis, False)

    def nonzero(self):
        indices = [i for i, v in enumerate(self._data) if v]
        if self.ndim == 1:
            return (ndarray(indices, dtype=_dtype_cls('int64')),)
        result = [[] for _ in range(self.ndim)]
        for flat_i in indices:
            multi = _unravel_index(flat_i, self._shape)
            for ax, ix in enumerate(multi):
                result[ax].append(ix)
        return tuple(ndarray(r, dtype=_dtype_cls('int64')) for r in result)

    def where_nonzero(self):
        return self.nonzero()

    def count_nonzero(self):
        return sum(1 for v in self._data if v)

    # ── element-wise math ─────────────────────────────────────────────────────

    def _ewise(self, other, fn):
        """Element-wise binary op, handles scalar and broadcast."""
        if isinstance(other, ndarray):
            if self._shape == other._shape:
                out = [fn(a, b) for a, b in zip(self._data, other._data)]
                return ndarray(out, dtype=self._dtype, shape=self._shape)
            # broadcast
            bs = _broadcast_shapes(self._shape, other._shape)
            a  = _broadcast_to(self, bs)
            b  = _broadcast_to(other, bs)
            out = [fn(x, y) for x, y in zip(a._data, b._data)]
            return ndarray(out, dtype=self._dtype, shape=bs)
        # scalar
        out = [fn(v, other) for v in self._data]
        return ndarray(out, dtype=self._dtype, shape=self._shape)

    def __add__(self, other):  return self._ewise(other, operator.add)
    def __radd__(self, other): return self._ewise(other, lambda a, b: b + a)
    def __sub__(self, other):  return self._ewise(other, operator.sub)
    def __rsub__(self, other): return self._ewise(other, lambda a, b: b - a)
    def __mul__(self, other):  return self._ewise(other, operator.mul)
    def __rmul__(self, other): return self._ewise(other, lambda a, b: b * a)
    def __truediv__(self, other):
        return self._ewise(other, lambda a, b: a / b if b != 0 else (float('inf') if a > 0 else float('-inf') if a < 0 else float('nan')))
    def __rtruediv__(self, other):
        return self._ewise(other, lambda a, b: b / a if a != 0 else float('inf'))
    def __floordiv__(self, other): return self._ewise(other, operator.floordiv)
    def __mod__(self, other):      return self._ewise(other, operator.mod)
    def __pow__(self, other):      return self._ewise(other, operator.pow)
    def __rpow__(self, other):     return self._ewise(other, lambda a, b: b ** a)
    def __neg__(self):
        return ndarray([-v for v in self._data], dtype=self._dtype, shape=self._shape)
    def __pos__(self):
        return self.copy()
    def __abs__(self):
        return ndarray([abs(v) for v in self._data], dtype=self._dtype, shape=self._shape)
    def __invert__(self):
        return ndarray([~int(v) if self._dtype.kind in ('i','u','b') else v
                        for v in self._data], dtype=self._dtype, shape=self._shape)

    # ── bitwise ───────────────────────────────────────────────────────────────
    def __and__(self, other):  return self._ewise(other, operator.and_)
    def __or__(self, other):   return self._ewise(other, operator.or_)
    def __xor__(self, other):  return self._ewise(other, operator.xor)
    def __lshift__(self, other): return self._ewise(other, operator.lshift)
    def __rshift__(self, other): return self._ewise(other, operator.rshift)

    # ── comparison ────────────────────────────────────────────────────────────
    def __eq__(self, other):
        if isinstance(other, ndarray):
            return ndarray([a == b for a, b in zip(self._data, other._data)],
                           dtype=_dtype_cls('bool'), shape=self._shape)
        return ndarray([v == other for v in self._data],
                       dtype=_dtype_cls('bool'), shape=self._shape)
    def __ne__(self, other):
        r = self.__eq__(other)
        return ndarray([not v for v in r._data], dtype=_dtype_cls('bool'), shape=self._shape)
    def __lt__(self, other):
        r = self._ewise(other, operator.lt)
        return ndarray(r._data, dtype=_dtype_cls('bool'), shape=r._shape)
    def __le__(self, other):
        r = self._ewise(other, operator.le)
        return ndarray(r._data, dtype=_dtype_cls('bool'), shape=r._shape)
    def __gt__(self, other):
        r = self._ewise(other, operator.gt)
        return ndarray(r._data, dtype=_dtype_cls('bool'), shape=r._shape)
    def __ge__(self, other):
        r = self._ewise(other, operator.ge)
        return ndarray(r._data, dtype=_dtype_cls('bool'), shape=r._shape)

    # ── matrix multiply ───────────────────────────────────────────────────────
    def __matmul__(self, other):
        return matmul(self, other)

    def dot(self, other):
        return matmul(self, other)

    # ── iteration ────────────────────────────────────────────────────────────
    def __iter__(self):
        if self.ndim == 0:
            raise TypeError("iteration over a 0-d array")
        size = _prod(self._shape[1:]) if self.ndim > 1 else 1
        for i in range(self._shape[0]):
            if self.ndim == 1:
                yield self._data[i]
            else:
                yield ndarray(self._data[i*size:(i+1)*size],
                              dtype=self._dtype, shape=self._shape[1:])

    def __len__(self):
        if self.ndim == 0:
            raise TypeError("len() of unsized object")
        return self._shape[0]

    def __bool__(self):
        if self.size != 1:
            raise ValueError("The truth value of an array with more than one element is ambiguous")
        return bool(self._data[0])

    def __float__(self):
        if self.size != 1:
            raise TypeError("only size-1 arrays can be converted to Python scalars")
        return float(self._data[0])

    def __int__(self):
        if self.size != 1:
            raise TypeError("only size-1 arrays can be converted to Python scalars")
        return int(self._data[0])

    def __complex__(self):
        if self.size != 1:
            raise TypeError("only size-1 arrays can be converted to Python scalars")
        return complex(self._data[0])

    def __contains__(self, item):
        return item in self._data

    def __repr__(self):
        if self.ndim == 0:
            return f"array({self._data[0]!r}, dtype={self._dtype})"
        return f"array({self.tolist()!r}, dtype={self._dtype})"

    def __str__(self):
        return str(self.tolist())

    def __hash__(self):
        raise TypeError("unhashable type: 'ndarray'")

    def __array__(self, dtype=None):
        """Allow numpy interop when numpy is present."""
        if _HAS_NUMPY:
            arr = _np.array(self.tolist())
            if dtype is not None:
                arr = arr.astype(str(dtype))
            return arr
        raise TypeError("NumPy not installed; cannot convert to np.ndarray")

    # ── concatenate helpers ───────────────────────────────────────────────────
    def __iadd__(self, other):
        r = self.__add__(other)
        self._data = r._data
        return self
    def __isub__(self, other):
        r = self.__sub__(other)
        self._data = r._data
        return self
    def __imul__(self, other):
        r = self.__mul__(other)
        self._data = r._data
        return self
    def __itruediv__(self, other):
        r = self.__truediv__(other)
        self._data = r._data
        return self

    # ── numpy-compatible extras ───────────────────────────────────────────────
    def conj(self):
        return ndarray([v.conjugate() if isinstance(v, complex) else v
                        for v in self._data], dtype=self._dtype, shape=self._shape)
    conjugate = conj

    def item(self, *args):
        if not args:
            if self.size != 1:
                raise ValueError("item() requires size-1 array or index")
            return self._data[0]
        return self._data[args[0]] if len(args) == 1 else \
               self._data[_ravel_index(args, self._shape)]

    def items(self):
        for i, v in enumerate(self._data):
            yield _unravel_index(i, self._shape), v

    def put(self, indices, values):
        if isinstance(indices, int):
            indices = [indices]
        if not hasattr(values, '__iter__'):
            values = [values] * len(indices)
        for i, v in zip(indices, values):
            self._data[i] = self._dtype.cast(v)

    def take(self, indices, axis=None):
        if axis is None:
            return ndarray([self._data[i] for i in (indices._data if isinstance(indices, ndarray) else indices)],
                           dtype=self._dtype)
        raise NotImplementedError("take with axis not yet supported")

    def repeat(self, repeats, axis=None):
        if axis is None:
            out = []
            for v in self._data:
                out.extend([v] * (repeats if isinstance(repeats, int) else repeats))
            return ndarray(out, dtype=self._dtype)
        raise NotImplementedError("repeat with axis not yet supported")

    def searchsorted(self, v, side='left'):
        data = sorted(self._data)
        if side == 'left':
            lo, hi = 0, len(data)
            while lo < hi:
                mid = (lo + hi) // 2
                if data[mid] < v:
                    lo = mid + 1
                else:
                    hi = mid
            return lo
        else:
            lo, hi = 0, len(data)
            while lo < hi:
                mid = (lo + hi) // 2
                if data[mid] <= v:
                    lo = mid + 1
                else:
                    hi = mid
            return lo

    def tofile(self, fid, sep='', format='%s'):
        raise NotImplementedError("tofile not supported in pure-Python mode")

    def dumps(self):
        import pickle
        return pickle.dumps(self)

    def dump(self, file):
        import pickle
        with open(file, 'wb') as f:
            pickle.dump(self, f)

    # --- numpy compat aliases --------------------------------------------------
    def sum_axis(self, axis):
        return self.sum(axis=axis)

    def __deepcopy__(self, memo):
        return self.copy()

    def __copy__(self):
        return self.copy()


# ── broadcast helper ──────────────────────────────────────────────────────────

def _broadcast_to(arr, shape):
    """Return a new ndarray broadcast to *shape* (no data copy if possible)."""
    if arr._shape == shape:
        return arr
    padded = (1,) * (len(shape) - len(arr._shape)) + arr._shape
    new_data = []
    for idx in _indices_for_shape(shape):
        src_idx = tuple(0 if padded[i] == 1 else idx[i] for i in range(len(shape)))
        new_data.append(arr._data[_ravel_index(src_idx, padded)])
    return ndarray(new_data, dtype=arr._dtype, shape=shape)


# ── matmul / dot ──────────────────────────────────────────────────────────────

def matmul(a, b):
    """Matrix multiplication for 1-D and 2-D arrays."""
    if not isinstance(a, ndarray):
        a = ndarray(a)
    if not isinstance(b, ndarray):
        b = ndarray(b)

    if a.ndim == 1 and b.ndim == 1:
        # dot product
        return sum(x * y for x, y in zip(a._data, b._data))

    if a.ndim == 2 and b.ndim == 2:
        M, K  = a._shape
        K2, N = b._shape
        if K != K2:
            raise ValueError(f"matmul shape mismatch: {a._shape} @ {b._shape}")
        out = [0.0] * (M * N)
        for i in range(M):
            for k in range(K):
                a_ik = a._data[i * K + k]
                for j in range(N):
                    out[i * N + j] += a_ik * b._data[k * N + j]
        return ndarray(out, dtype=_dtype_cls('float64'), shape=(M, N))

    if a.ndim == 2 and b.ndim == 1:
        M, K = a._shape
        out = [sum(a._data[i*K+k] * b._data[k] for k in range(K)) for i in range(M)]
        return ndarray(out, dtype=_dtype_cls('float64'))

    if a.ndim == 1 and b.ndim == 2:
        K, N = b._shape
        out = [sum(a._data[k] * b._data[k*N+j] for k in range(K)) for j in range(N)]
        return ndarray(out, dtype=_dtype_cls('float64'))

    raise NotImplementedError(f"matmul for ndim={a.ndim},{b.ndim} not yet supported")


# ── array creation functions ──────────────────────────────────────────────────

def array(obj, dtype=None, copy=True, order='C', ndmin=0):
    if isinstance(obj, ndarray) and not copy and dtype is None:
        return obj
    return ndarray(obj, dtype=dtype)

def asarray(a, dtype=None, order=None):
    if isinstance(a, ndarray) and (dtype is None or a.dtype == _dtype_cls(dtype)):
        return a
    return ndarray(a, dtype=dtype)

def ascontiguousarray(a, dtype=None):
    return asarray(a, dtype=dtype)

def asfortranarray(a, dtype=None):
    return asarray(a, dtype=dtype)

def zeros(shape, dtype='float64', order='C'):
    if isinstance(shape, int):
        shape = (shape,)
    dt = _dtype_cls(dtype)
    return ndarray([dt.cast(0)] * _prod(shape), dtype=dt, shape=tuple(shape))

def ones(shape, dtype='float64', order='C'):
    if isinstance(shape, int):
        shape = (shape,)
    dt = _dtype_cls(dtype)
    return ndarray([dt.cast(1)] * _prod(shape), dtype=dt, shape=tuple(shape))

def full(shape, fill_value, dtype=None, order='C'):
    if isinstance(shape, int):
        shape = (shape,)
    if dtype is None:
        if isinstance(fill_value, bool):
            dtype = 'bool'
        elif isinstance(fill_value, int):
            dtype = 'int64'
        elif isinstance(fill_value, float):
            dtype = 'float64'
        elif isinstance(fill_value, complex):
            dtype = 'complex128'
        else:
            dtype = 'object'
    dt = _dtype_cls(dtype)
    return ndarray([dt.cast(fill_value)] * _prod(shape), dtype=dt, shape=tuple(shape))

def empty(shape, dtype='float64', order='C'):
    return zeros(shape, dtype=dtype)

def zeros_like(a, dtype=None, order='C'):
    dt = _dtype_cls(dtype) if dtype else a.dtype
    return zeros(a.shape, dtype=dt)

def ones_like(a, dtype=None, order='C'):
    dt = _dtype_cls(dtype) if dtype else a.dtype
    return ones(a.shape, dtype=dt)

def full_like(a, fill_value, dtype=None, order='C'):
    dt = _dtype_cls(dtype) if dtype else a.dtype
    return full(a.shape, fill_value, dtype=dt)

def empty_like(a, dtype=None, order='C'):
    return zeros_like(a, dtype=dtype)

def eye(N, M=None, k=0, dtype='float64'):
    if M is None:
        M = N
    dt = _dtype_cls(dtype)
    data = []
    for i in range(N):
        for j in range(M):
            data.append(dt.cast(1 if j - i == k else 0))
    return ndarray(data, dtype=dt, shape=(N, M))

def identity(n, dtype='float64'):
    return eye(n, dtype=dtype)

def arange(start, stop=None, step=1, dtype=None):
    if stop is None:
        start, stop = 0, start
    vals = []
    v = start
    if step > 0:
        while v < stop:
            vals.append(v)
            v += step
    else:
        while v > stop:
            vals.append(v)
            v += step
    if dtype is None:
        dtype = 'float64' if isinstance(step, float) or isinstance(start, float) else 'int64'
    return ndarray(vals, dtype=dtype)

def linspace(start, stop, num=50, endpoint=True, retstep=False, dtype=None):
    if num == 0:
        arr = ndarray([], dtype=dtype or 'float64')
        return (arr, 0.0) if retstep else arr
    if num == 1:
        arr = ndarray([float(start)], dtype=dtype or 'float64')
        return (arr, 0.0) if retstep else arr
    step = (stop - start) / (num - 1 if endpoint else num)
    vals = [start + step * i for i in range(num)]
    if endpoint:
        vals[-1] = stop
    arr = ndarray(vals, dtype=dtype or 'float64')
    return (arr, step) if retstep else arr

def logspace(start, stop, num=50, endpoint=True, base=10.0, dtype=None):
    lin = linspace(start, stop, num=num, endpoint=endpoint)
    vals = [base ** v for v in lin._data]
    return ndarray(vals, dtype=dtype or 'float64')

def geomspace(start, stop, num=50, endpoint=True, dtype=None):
    log_start = math.log10(start)
    log_stop  = math.log10(stop)
    return logspace(log_start, log_stop, num=num, endpoint=endpoint, base=10.0, dtype=dtype)

def diag(v, k=0):
    if isinstance(v, ndarray) and v.ndim == 1:
        n = len(v._data) + abs(k)
        out = zeros((n, n))
        for i, val in enumerate(v._data):
            r, c = (i, i+k) if k >= 0 else (i-k, i)
            out._data[_ravel_index((r, c), (n, n))] = val
        return out
    elif isinstance(v, ndarray) and v.ndim == 2:
        return v.diagonal(k)
    raise ValueError("Input must be 1-D or 2-D")

def diagflat(v, k=0):
    flat = ndarray(v).ravel()
    return diag(flat, k)

def tril(m, k=0):
    m = asarray(m)
    rows, cols = m._shape[-2], m._shape[-1]
    data = list(m._data)
    for i in range(rows):
        for j in range(cols):
            if j - i > k:
                data[_ravel_index((i, j), (rows, cols))] = 0
    return ndarray(data, dtype=m.dtype, shape=m._shape)

def triu(m, k=0):
    m = asarray(m)
    rows, cols = m._shape[-2], m._shape[-1]
    data = list(m._data)
    for i in range(rows):
        for j in range(cols):
            if j - i < k:
                data[_ravel_index((i, j), (rows, cols))] = 0
    return ndarray(data, dtype=m.dtype, shape=m._shape)

def vander(x, N=None, increasing=False):
    x = asarray(x)
    n = len(x._data)
    if N is None:
        N = n
    out = []
    for xi in x._data:
        row = [xi**(N-1-j) if not increasing else xi**j for j in range(N)]
        out.extend(row)
    return ndarray(out, dtype=_dtype_cls('float64'), shape=(n, N))

def meshgrid(*xi, indexing='xy'):
    arrays = [asarray(x) for x in xi]
    if indexing == 'xy' and len(arrays) >= 2:
        arrays[0], arrays[1] = arrays[1], arrays[0]
    shapes = [a._shape[0] for a in arrays]
    grids = []
    for i, a in enumerate(arrays):
        shape = [1] * len(arrays)
        shape[i] = shapes[i]
        g = a.reshape(tuple(shape))
        target = list(shapes)
        target[i] = shapes[i]
        grids.append(_broadcast_to(g, tuple(target)))
    if indexing == 'xy' and len(grids) >= 2:
        grids[0], grids[1] = grids[1], grids[0]
    return grids

def mgrid_func(*slices):
    """Simplified mgrid — call as mgrid[0:3, 0:4]."""
    raise NotImplementedError("Use meshgrid instead of mgrid in numpy2 pure mode")

def ogrid_func(*slices):
    raise NotImplementedError("Use linspace/arange instead of ogrid in numpy2 pure mode")

def indices(dimensions, dtype='int64'):
    grids = meshgrid(*[arange(d) for d in dimensions], indexing='ij')
    return ndarray([g._data for g in grids], dtype=dtype,
                   shape=(len(dimensions),) + tuple(dimensions))

def fromiter(iterable, dtype, count=-1):
    data = list(iterable) if count < 0 else list(itertools.islice(iterable, count))
    return ndarray(data, dtype=dtype)

def frombuffer(buffer, dtype='float64', count=-1, offset=0):
    import struct as _struct
    dt = _dtype_cls(dtype)
    fmt = dt._fmt
    if fmt is None:
        raise TypeError(f"frombuffer not supported for dtype {dtype}")
    buf = bytes(buffer)[offset:]
    size = _struct.calcsize(fmt)
    n    = len(buf) // size if count < 0 else count
    vals = [_struct.unpack_from(fmt, buf, i*size)[0] for i in range(n)]
    return ndarray(vals, dtype=dt)

def fromfunction(fn, shape, dtype='float64', **kwargs):
    out = []
    for idx in _indices_for_shape(shape):
        out.append(fn(*idx, **kwargs))
    return ndarray(out, dtype=dtype, shape=shape)

def fromstring(string, dtype='float64', count=-1, sep=' '):
    parts = string.split(sep)
    if count > 0:
        parts = parts[:count]
    dt = _dtype_cls(dtype)
    return ndarray([dt.cast(p.strip()) for p in parts if p.strip()], dtype=dt)

# ── path safety helpers ─────────────────────────────────────────────────────────

def _safe_path(fname, writable=False):
    """Resolve and validate a file path to prevent directory traversal."""
    import os as _os
    resolved = _os.path.abspath(_os.path.normpath(fname))
    # Basic check: no null bytes, no embedded drive access tricks
    if '\x00' in fname:
        raise ValueError("Null byte in file path")
    if not isinstance(fname, (str, bytes)):
        raise TypeError("File path must be a string or bytes")
    return resolved


# ── pickle safe-load helper ─────────────────────────────────────────────────────

def _safe_load(file_obj):
    """Load data from a pickle file with restricted deserialization.

    Only permits basic Python types and numpy2 ndarray to be unpickled,
    preventing arbitrary code execution via malicious pickle data.
    """
    import pickle
    import io
    data = file_obj.read()
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    class _RestrictedUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            # Whitelist of safe modules and types
            ALLOWED_MODULES = {
                'builtins',
                '_collections_abc',
                'copyreg',
                'enum',
                'types',
            }
            ALLOWED_TYPES = {
                # Standard Python types
                'bool', 'int', 'float', 'complex', 'str', 'bytes', 'bytearray',
                'list', 'tuple', 'set', 'frozenset', 'dict', 'NoneType',
                'slice', 'range', 'property', 'staticmethod', 'classmethod',
                # Collections
                'OrderedDict', 'defaultdict', 'Counter', 'deque',
            }
            # Allow numpy2 ndarray
            if module == 'numpy2.array' and name in ('ndarray',):
                return super().find_class(module, name)
            # Allow standard library
            if module in ALLOWED_MODULES:
                return super().find_class(module, name)
            if module == 'builtins' and name in ALLOWED_TYPES:
                return super().find_class(module, name)
            if module.startswith('numpy2.'):
                # Allow numpy2 types
                return super().find_class(module, name)
            raise pickle.UnpicklingError(
                f"Unsafe deserialization blocked: module='{module}', name='{name}'. "
                "Use allow_pickle=True to enable arbitrary pickle loading."
            )

    return _RestrictedUnpickler(buf).load()


def loadtxt(fname, dtype='float64', delimiter=None, skiprows=0, usecols=None, encoding=None):
    _safe_path(fname)
    import csv
    rows = []
    with open(fname, newline='', encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter or ' ')
        for _ in range(skiprows):
            next(reader)
        for row in reader:
            if usecols is not None:
                row = [row[c] for c in usecols]
            rows.append([float(v) for v in row if v.strip()])
    return ndarray(rows, dtype=dtype)

def savetxt(fname, X, fmt='%.18e', delimiter=' ', newline='\n', header='', footer='', encoding=None):
    _safe_path(fname, writable=True)
    X = asarray(X)
    with open(fname, 'w', encoding=encoding or 'utf-8') as f:
        if header:
            f.write('# ' + header + newline)
        for row in X:
            if isinstance(row, ndarray):
                f.write(delimiter.join(fmt % v for v in row._data) + newline)
            else:
                f.write(fmt % row + newline)
        if footer:
            f.write('# ' + footer + newline)

def load(file, allow_pickle=False):
    """Load array from a .npy file using pickle.

    Parameters
    ----------
    file : str or path-like
        File path.
    allow_pickle : bool, default False
        If True, use standard pickle.load() (potentially unsafe).
        If False (default), use a restricted unpickler that only allows
        safe built-in types and numpy2.ndarray.

    Warning
    -------
    Pickle files can execute arbitrary code. Only load files you trust.
    """
    import warnings as _warnings
    resolved = _safe_path(file)
    with open(resolved, 'rb') as f:
        if allow_pickle:
            _warnings.warn(
                "load(allow_pickle=True): loading untrusted pickle data can "
                "execute arbitrary code. Use with caution.",
                UserWarning, stacklevel=2,
            )
            import pickle
            return pickle.load(f)
        return _safe_load(f)

def save(file, arr, allow_pickle=False):
    _safe_path(file, writable=True)
    import pickle
    if not file.endswith('.npy'):
        file += '.npy'
    with open(file, 'wb') as f:
        pickle.dump(arr, f)

def savez(file, *args, **kwargs):
    _safe_path(file, writable=True)
    import pickle
    arrays = {f'arr_{i}': a for i, a in enumerate(args)}
    arrays.update(kwargs)
    with open(file + '.npz', 'wb') as f:
        pickle.dump(arrays, f)


# ── shape / joining ───────────────────────────────────────────────────────────

def concatenate(arrays, axis=0):
    arrays = [asarray(a) for a in arrays]
    if not arrays:
        return ndarray([], dtype='float64')
    if axis == 0 or arrays[0].ndim == 1:
        data = []
        for a in arrays:
            data.extend(a._data)
        new_shape = (sum(a._shape[0] for a in arrays),) + arrays[0]._shape[1:]
        return ndarray(data, dtype=arrays[0].dtype, shape=new_shape)
    raise NotImplementedError("concatenate with axis != 0 not yet fully supported")

def stack(arrays, axis=0):
    arrays = [asarray(a) for a in arrays]
    expanded = [a.expand_dims(axis) for a in arrays]
    return concatenate(expanded, axis=axis)

def vstack(tup):
    arrays = [asarray(a) for a in tup]
    if arrays[0].ndim == 1:
        arrays = [a.reshape(1, -1) for a in arrays]
    return concatenate(arrays, axis=0)

def hstack(tup):
    arrays = [asarray(a) for a in tup]
    if arrays[0].ndim == 1:
        data = []
        for a in arrays:
            data.extend(a._data)
        return ndarray(data, dtype=arrays[0].dtype)
    return concatenate(arrays, axis=1)

def dstack(tup):
    arrays = [asarray(a) for a in tup]
    if arrays[0].ndim < 3:
        arrays = [a.reshape(a._shape + (1,)) for a in arrays]
    return concatenate(arrays, axis=2)

def column_stack(tup):
    arrays = [asarray(a) for a in tup]
    if arrays[0].ndim == 1:
        arrays = [a.reshape(-1, 1) for a in arrays]
    return concatenate(arrays, axis=1)

def row_stack(tup):
    return vstack(tup)

def split(ary, indices_or_sections, axis=0):
    ary = asarray(ary)
    n = ary._shape[axis] if axis < ary.ndim else ary.size
    if isinstance(indices_or_sections, int):
        size = n // indices_or_sections
        indices = [i * size for i in range(1, indices_or_sections)]
    else:
        indices = list(indices_or_sections)
    result = []
    prev = 0
    for idx in indices + [n]:
        if axis == 0 and ary.ndim == 1:
            result.append(ary[prev:idx])
        elif axis == 0:
            result.append(ary[prev:idx])
        prev = idx
    return result

def hsplit(ary, indices_or_sections):
    return split(ary, indices_or_sections, axis=1)

def vsplit(ary, indices_or_sections):
    return split(ary, indices_or_sections, axis=0)

def dsplit(ary, indices_or_sections):
    return split(ary, indices_or_sections, axis=2)

def tile(A, reps):
    A = asarray(A)
    if isinstance(reps, int):
        reps = (reps,)
    data = list(A._data) * _prod(reps)
    new_shape = tuple(s * r for s, r in zip(A._shape, reps))
    return ndarray(data[:_prod(new_shape)], dtype=A.dtype, shape=new_shape)

def repeat(a, repeats, axis=None):
    a = asarray(a)
    return a.repeat(repeats, axis=axis)

def unique(ar, return_index=False, return_inverse=False, return_counts=False, axis=None):
    ar = asarray(ar)
    seen = {}
    order = []
    for i, v in enumerate(ar._data):
        if v not in seen:
            seen[v] = i
            order.append(v)
    unique_vals = sorted(order)
    u = ndarray(unique_vals, dtype=ar.dtype)
    results = [u]
    if return_index:
        results.append(ndarray([seen[v] for v in unique_vals], dtype=_dtype_cls('int64')))
    if return_inverse:
        inv_map = {v: i for i, v in enumerate(unique_vals)}
        results.append(ndarray([inv_map[v] for v in ar._data], dtype=_dtype_cls('int64')))
    if return_counts:
        from collections import Counter
        cnt = Counter(ar._data)
        results.append(ndarray([cnt[v] for v in unique_vals], dtype=_dtype_cls('int64')))
    return tuple(results) if len(results) > 1 else results[0]

def flip(m, axis=None):
    m = asarray(m)
    if axis is None:
        return ndarray(list(reversed(m._data)), dtype=m.dtype, shape=m._shape)
    new_data = list(m._data)
    for idx in _indices_for_shape(m._shape):
        new_idx = list(idx)
        new_idx[axis] = m._shape[axis] - 1 - idx[axis]
        new_data[_ravel_index(tuple(new_idx), m._shape)] = \
            m._data[_ravel_index(idx, m._shape)]
    return ndarray(new_data, dtype=m.dtype, shape=m._shape)

def fliplr(m):
    return flip(m, axis=1)

def flipud(m):
    return flip(m, axis=0)

def rot90(m, k=1, axes=(0, 1)):
    m = asarray(m)
    k = k % 4
    for _ in range(k):
        m = flip(m.transpose(*([i for i in range(m.ndim) if i not in axes] + list(axes))), axis=axes[1])
    return m

def roll(a, shift, axis=None):
    a = asarray(a)
    if axis is None:
        data = list(a._data)
        n = len(data)
        shift = shift % n
        return ndarray(data[-shift:] + data[:-shift], dtype=a.dtype, shape=a._shape)
    raise NotImplementedError("roll with axis not yet supported")

def pad(array, pad_width, mode='constant', **kwargs):
    array = asarray(array)
    constant_values = kwargs.get('constant_values', 0)
    if isinstance(pad_width, int):
        pad_width = [(pad_width, pad_width)] * array.ndim
    elif isinstance(pad_width, tuple) and len(pad_width) == 2 and isinstance(pad_width[0], int):
        pad_width = [pad_width] * array.ndim

    new_shape = tuple(s + p[0] + p[1] for s, p in zip(array._shape, pad_width))
    new_data  = [constant_values] * _prod(new_shape)
    for idx in _indices_for_shape(array._shape):
        new_idx = tuple(idx[i] + pad_width[i][0] for i in range(array.ndim))
        new_data[_ravel_index(new_idx, new_shape)] = array._data[_ravel_index(idx, array._shape)]
    return ndarray(new_data, dtype=array.dtype, shape=new_shape)

def broadcast_to(array, shape):
    array = asarray(array)
    return _broadcast_to(array, shape)

def broadcast_arrays(*args):
    arrays = [asarray(a) for a in args]
    shape = _broadcast_shapes(*[a._shape for a in arrays])
    return [_broadcast_to(a, shape) for a in arrays]

def expand_dims(a, axis):
    return asarray(a).expand_dims(axis)

def squeeze(a, axis=None):
    return asarray(a).squeeze(axis)

def atleast_1d(*arys):
    result = []
    for a in arys:
        a = asarray(a)
        if a.ndim == 0:
            a = a.reshape((1,))
        result.append(a)
    return result[0] if len(result) == 1 else result

def atleast_2d(*arys):
    result = []
    for a in arys:
        a = asarray(a)
        if a.ndim < 2:
            a = a.reshape((1,) * (2 - a.ndim) + a._shape)
        result.append(a)
    return result[0] if len(result) == 1 else result

def atleast_3d(*arys):
    result = []
    for a in arys:
        a = asarray(a)
        while a.ndim < 3:
            a = a.reshape((1,) + a._shape)
        result.append(a)
    return result[0] if len(result) == 1 else result


# ── searching / sorting ───────────────────────────────────────────────────────

def where(condition, x=None, y=None):
    condition = asarray(condition)
    if x is None and y is None:
        return condition.nonzero()
    x = asarray(x) if not isinstance(x, (int, float, complex)) else x
    y = asarray(y) if not isinstance(y, (int, float, complex)) else y
    x_data = x._data if isinstance(x, ndarray) else [x] * condition.size
    y_data = y._data if isinstance(y, ndarray) else [y] * condition.size
    out = [xv if cv else yv for cv, xv, yv in zip(condition._data, x_data, y_data)]
    return ndarray(out, shape=condition._shape)

def select(condlist, choicelist, default=0):
    n = len(condlist[0]._data) if isinstance(condlist[0], ndarray) else 1
    out = [default] * n
    for cond, choice in zip(condlist, choicelist):
        cdata = cond._data if isinstance(cond, ndarray) else [cond]*n
        vdata = choice._data if isinstance(choice, ndarray) else [choice]*n
        for i, (c, v) in enumerate(zip(cdata, vdata)):
            if c and out[i] == default:
                out[i] = v
    return ndarray(out)

def argwhere(a):
    a = asarray(a)
    result = []
    for i, v in enumerate(a._data):
        if v:
            result.append(list(_unravel_index(i, a._shape)))
    return ndarray(result, dtype=_dtype_cls('int64'),
                   shape=(len(result), a.ndim)) if result else \
           ndarray([], dtype=_dtype_cls('int64'), shape=(0, a.ndim))

def argmax(a, axis=None):
    return asarray(a).argmax(axis)

def argmin(a, axis=None):
    return asarray(a).argmin(axis)

def argsort(a, axis=-1, kind='quicksort'):
    return asarray(a).argsort(axis, kind)

def sort(a, axis=-1, kind='quicksort'):
    a = asarray(a).copy()
    a.sort(axis, kind)
    return a

def lexsort(keys):
    n = len(keys[0]._data) if isinstance(keys[0], ndarray) else len(keys[0])
    rows = list(range(n))
    for key in reversed(keys):
        kdata = key._data if isinstance(key, ndarray) else list(key)
        rows.sort(key=lambda i: kdata[i])
    return ndarray(rows, dtype=_dtype_cls('int64'))

def searchsorted(a, v, side='left', sorter=None):
    return asarray(a).searchsorted(v, side)

def count_nonzero(a, axis=None):
    a = asarray(a)
    if axis is None:
        return a.count_nonzero()
    raise NotImplementedError("count_nonzero with axis not yet supported")

def flatnonzero(a):
    a = asarray(a)
    return ndarray([i for i, v in enumerate(a._data) if v], dtype=_dtype_cls('int64'))

def nonzero(a):
    return asarray(a).nonzero()


# ── type-testing ──────────────────────────────────────────────────────────────

def isnan(x):
    if isinstance(x, ndarray):
        return ndarray([_is_nan(v) for v in x._data], dtype=_dtype_cls('bool'), shape=x._shape)
    return _is_nan(x)

def isinf(x):
    if isinstance(x, ndarray):
        return ndarray([_is_inf(v) for v in x._data], dtype=_dtype_cls('bool'), shape=x._shape)
    return _is_inf(x)

def isfinite(x):
    if isinstance(x, ndarray):
        return ndarray([not (_is_nan(v) or _is_inf(v)) for v in x._data],
                       dtype=_dtype_cls('bool'), shape=x._shape)
    return not (_is_nan(x) or _is_inf(x))

def isneginf(x):
    if isinstance(x, ndarray):
        return ndarray([v == float('-inf') for v in x._data], dtype=_dtype_cls('bool'), shape=x._shape)
    return x == float('-inf')

def isposinf(x):
    if isinstance(x, ndarray):
        return ndarray([v == float('inf') for v in x._data], dtype=_dtype_cls('bool'), shape=x._shape)
    return x == float('inf')

def isreal(x):
    if isinstance(x, ndarray):
        return ndarray([not isinstance(v, complex) or v.imag == 0 for v in x._data],
                       dtype=_dtype_cls('bool'), shape=x._shape)
    return not isinstance(x, complex) or x.imag == 0

def iscomplex(x):
    if isinstance(x, ndarray):
        return ndarray([isinstance(v, complex) and v.imag != 0 for v in x._data],
                       dtype=_dtype_cls('bool'), shape=x._shape)
    return isinstance(x, complex) and x.imag != 0

def isscalar(element):
    return isinstance(element, (int, float, complex, bool, str, bytes))

def isclose(a, b, rtol=1e-5, atol=1e-8, equal_nan=False):
    a, b = asarray(a), asarray(b)
    def _close(x, y):
        if equal_nan and _is_nan(x) and _is_nan(y):
            return True
        if _is_nan(x) or _is_nan(y):
            return False
        return abs(x - y) <= atol + rtol * abs(y)
    return ndarray([_close(x, y) for x, y in zip(a._data, b._data)],
                   dtype=_dtype_cls('bool'), shape=a._shape)

def allclose(a, b, rtol=1e-5, atol=1e-8, equal_nan=False):
    r = isclose(a, b, rtol=rtol, atol=atol, equal_nan=equal_nan)
    return all(r._data)

def array_equal(a1, a2, equal_nan=False):
    a1, a2 = asarray(a1), asarray(a2)
    if a1._shape != a2._shape:
        return False
    for x, y in zip(a1._data, a2._data):
        if equal_nan and _is_nan(x) and _is_nan(y):
            continue
        if x != y:
            return False
    return True

def array_equiv(a1, a2):
    try:
        bs = _broadcast_shapes(a1._shape, a2._shape)
        return array_equal(_broadcast_to(a1, bs), _broadcast_to(a2, bs))
    except Exception:
        return False

def may_share_memory(a, b):
    return False  # pure Python, no shared memory

def shares_memory(a, b):
    return False


# ── type conversions ──────────────────────────────────────────────────────────

def result_type(*arrays_and_dtypes):
    from .dtypes import result_type as _rt
    return _rt(*arrays_and_dtypes)

def can_cast(from_, to, casting='safe'):
    return True  # simplified

def common_type(*arrays):
    from .dtypes import result_type as _rt
    return _rt(*arrays)

def min_scalar_type(a):
    if isinstance(a, bool):
        return _dtype_cls('bool')
    if isinstance(a, int):
        return _dtype_cls('int64')
    if isinstance(a, float):
        return _dtype_cls('float64')
    return _dtype_cls('object')

def promote_types(type1, type2):
    return result_type(_dtype_cls(type1), _dtype_cls(type2))


# ── misc ──────────────────────────────────────────────────────────────────────

def shape(a):
    return asarray(a).shape

def ndim(a):
    return asarray(a).ndim

def size(a, axis=None):
    a = asarray(a)
    if axis is None:
        return a.size
    return a._shape[axis]

def copyto(dst, src, casting='same_kind', where=None):
    src = asarray(src)
    dst._data = [dst.dtype.cast(v) for v in src._data]

def iterable(y):
    try:
        iter(y)
        return True
    except TypeError:
        return False

def unravel_index(indices, shape):
    if isinstance(indices, int):
        return _unravel_index(indices, shape)
    return tuple(ndarray([_unravel_index(i, shape)[ax] for i in indices],
                         dtype=_dtype_cls('int64'))
                 for ax in range(len(shape)))

def ravel_multi_index(multi_index, dims, mode='raise', order='C'):
    result = []
    for row in zip(*[m._data if isinstance(m, ndarray) else m for m in multi_index]):
        result.append(_ravel_index(row, dims))
    return ndarray(result, dtype=_dtype_cls('int64'))

def ix_(*args):
    result = []
    n = len(args)
    for i, a in enumerate(args):
        a = asarray(a)
        shape = [1] * n
        shape[i] = len(a._data)
        result.append(a.reshape(tuple(shape)))
    return tuple(result)

def ndindex(*shape):
    return _indices_for_shape(shape)

def ndenumerate(a):
    a = asarray(a)
    for i, v in enumerate(a._data):
        yield _unravel_index(i, a._shape), v

def apply_along_axis(func1d, axis, arr, *args, **kwargs):
    arr = asarray(arr)
    n = arr._shape[axis]
    results = []
    for i in range(arr._shape[0] if axis != 0 else arr._shape[1] if arr.ndim > 1 else n):
        if axis == 0:
            if arr.ndim == 1:
                row = ndarray([arr._data[i]], dtype=arr.dtype)
            else:
                row = arr[i]
        else:
            row = ndarray([arr._data[j * arr._shape[1] + i] for j in range(arr._shape[0])],
                          dtype=arr.dtype)
        results.append(func1d(row, *args, **kwargs))
    return ndarray(results)

def apply_over_axes(func, a, axes):
    a = asarray(a)
    for axis in axes:
        a = func(a, axis=axis)
    return a

def vectorize(pyfunc, otypes=None, excluded=None, cache=False, signature=None):
    def _vec(*args):
        arrays = [asarray(a) if not isinstance(a, (int, float, complex)) else a for a in args]
        ref = next((a for a in arrays if isinstance(a, ndarray)), None)
        if ref is None:
            return pyfunc(*args)
        size = ref.size
        data_iters = [(a._data if isinstance(a, ndarray) else [a]*size) for a in arrays]
        result = [pyfunc(*vals) for vals in zip(*data_iters)]
        dt = _dtype_cls(otypes[0]) if otypes else None
        return ndarray(result, dtype=dt, shape=ref._shape)
    return _vec

def frompyfunc(func, nin, nout):
    def _wrap(*args):
        arrays = [asarray(a) for a in args]
        ref = arrays[0]
        rows = zip(*[a._data for a in arrays])
        out = [func(*vs) for vs in rows]
        return ndarray(out, shape=ref._shape)
    return _wrap
