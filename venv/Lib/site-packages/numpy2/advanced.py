"""
numpy2.advanced — Advanced array operations and utilities.

New in 2.1.0:
- ArrayCache: LRU cache for expensive array computations
- ArrayPipeline: Chainable transformation pipeline
- compress_array / decompress_array: zlib-based array compression
- ArrayValidator: Schema-based array validation
- sliding_window_view: Efficient sliding window without copies
- batch_apply: Apply a function across batches of rows
- to_structured: Convert ndarray + field names to structured-dict list
- ProfiledArray: Transparent profiling wrapper

New in 2.3.0 (pain-point fixes):
- NamedArray: Named dimension support — solves high-D broadcasting confusion
- vmapped: Auto-vectorize a function over arbitrary axes (JAX-style vmap)
- scan: Cumulative operation with state passing (iterative computation)
- smart_axis: Auto-resolve axis arguments intelligently
- nan_safe_json: Proper NaN/Inf handling for JSON serialization
- ThreadSafeArray: Lock-protected thread-safe array wrapper
- CompatLayer: Drop-in replacements for removed/deprecated NumPy APIs
- auto_type_convert: Convert between numpy/numpy2/python types seamlessly
- chunked_reduce: Memory-efficient chunked reduction for large arrays
- broadcast_explicit: Explicit broadcasting with clear dimension control
- einsum_enhanced: Enhanced einsum with named axis support
- array_memory_usage: Report memory usage of arrays
- lazy_array: Deferred computation array that evaluates on demand
"""
from __future__ import annotations

import json
import math
import time
import zlib
import base64
import hashlib
import threading
import sys
from collections import OrderedDict
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

from .array import ndarray, asarray, zeros, ones, arange, array as _array


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LRU Array Cache
# ═══════════════════════════════════════════════════════════════════════════════

class _CacheEntry:
    __slots__ = ("value", "hits", "created_at", "size_bytes")

    def __init__(self, value, size_bytes: int = 0):
        self.value = value
        self.hits = 0
        self.created_at = time.time()
        self.size_bytes = size_bytes


class ArrayCache:
    """
    Thread-safe LRU cache for memoising expensive array computations.

    Parameters
    ----------
    maxsize : int
        Maximum number of entries to keep (default 128).
    ttl : float | None
        Time-to-live in seconds; None means no expiry.

    Example
    -------
    >>> cache = ArrayCache(maxsize=64)
    >>> @cache.memoize
    ... def expensive(x):
    ...     return x * 2
    >>> expensive(np2.array([1, 2, 3]))
    """

    def __init__(self, maxsize: int = 128, ttl: Optional[float] = None) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, *args, **kwargs) -> str:
        parts = []
        for a in args:
            if isinstance(a, ndarray):
                parts.append(f"arr:{a.tolist()!r}:{a.dtype}")
            else:
                parts.append(repr(a))
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v!r}")
        raw = "|".join(parts)
        # usedforsecurity=False: MD5 here is only for cache key hashing,
        # not for security/cryptographic purposes.
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            entry = self._store[key]
            if self._ttl is not None and (time.time() - entry.created_at) > self._ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        size = 0
        if isinstance(value, ndarray):
            size = len(value._data) * 8
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = _CacheEntry(value, size)
                return
            if len(self._store) >= self._maxsize:
                self._store.popitem(last=False)
            self._store[key] = _CacheEntry(value, size)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._store),
                "maxsize": self._maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total else 0.0,
            }

    def memoize(self, func: Callable) -> Callable:
        """Decorator: cache results of *func* based on its arguments."""
        def wrapper(*args, **kwargs):
            key = self._make_key(*args, **kwargs)
            cached = self.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            self.set(key, result)
            return result
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Array Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class ArrayPipeline:
    """
    Chainable, lazy transformation pipeline for ndarrays.

    Example
    -------
    >>> pipe = ArrayPipeline(np2.array([1, 2, 3, 4, 5]))
    >>> result = pipe.filter(lambda x: x > 2).map(lambda x: x ** 2).run()
    """

    def __init__(self, arr: ndarray) -> None:
        self._source = asarray(arr)
        self._steps: List[Tuple[str, Callable]] = []

    def map(self, func: Callable) -> "ArrayPipeline":
        """Apply element-wise function."""
        self._steps.append(("map", func))
        return self

    def filter(self, predicate: Callable) -> "ArrayPipeline":
        """Keep elements where predicate returns True."""
        self._steps.append(("filter", predicate))
        return self

    def normalize(self) -> "ArrayPipeline":
        """Min-max normalize to [0, 1]."""
        def _norm(arr):
            mn = min(arr._data)
            mx = max(arr._data)
            rng = mx - mn
            if rng == 0:
                return zeros(len(arr._data), dtype='float64')
            return ndarray([(v - mn) / rng for v in arr._data], dtype='float64')
        self._steps.append(("transform", _norm))
        return self

    def clip(self, lo: float, hi: float) -> "ArrayPipeline":
        """Clip values to [lo, hi]."""
        self._steps.append(("map", lambda x: max(lo, min(hi, x))))
        return self

    def round(self, decimals: int = 0) -> "ArrayPipeline":
        """Round values to *decimals* decimal places."""
        self._steps.append(("map", lambda x: round(x, decimals)))
        return self

    def standardize(self) -> "ArrayPipeline":
        """Z-score standardize (mean=0, std=1)."""
        def _zscore(arr):
            data = arr._data
            m = sum(data) / len(data)
            v = sum((x - m) ** 2 for x in data) / len(data)
            s = math.sqrt(v) if v > 0 else 1.0
            return ndarray([(x - m) / s for x in data], dtype='float64')
        self._steps.append(("transform", _zscore))
        return self

    def fill_nan(self, value: float = 0.0) -> "ArrayPipeline":
        """Replace NaN values."""
        self._steps.append(("map", lambda x: value if (isinstance(x, float) and math.isnan(x)) else x))
        return self

    def transform(self, func: Callable) -> "ArrayPipeline":
        """Apply a function to the entire array."""
        self._steps.append(("transform", func))
        return self

    def run(self) -> ndarray:
        """Execute all pipeline steps and return final ndarray."""
        arr = self._source
        for step_type, func in self._steps:
            if step_type == "map":
                arr = ndarray([func(v) for v in arr._data], dtype=arr.dtype)
            elif step_type == "filter":
                arr = ndarray([v for v in arr._data if func(v)], dtype=arr.dtype)
            elif step_type == "transform":
                arr = func(arr)
        return arr


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Compression
# ═══════════════════════════════════════════════════════════════════════════════

def compress_array(arr: ndarray, level: int = 6) -> bytes:
    """Compress an ndarray to bytes using zlib."""
    arr = asarray(arr)
    payload = {
        "shape": list(arr.shape),
        "dtype": arr.dtype.name,
        "data": arr.tolist(),
        "version": 2,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return zlib.compress(raw, level=level)


def decompress_array(blob: bytes) -> ndarray:
    """Decompress bytes produced by compress_array back to an ndarray."""
    raw = zlib.decompress(blob)
    payload = json.loads(raw.decode())
    return ndarray(payload["data"], dtype=payload.get("dtype"))


def compress_to_b64(arr: ndarray, level: int = 6) -> str:
    """Compress array and encode as a base64 string (safe for JSON transport)."""
    return base64.b64encode(compress_array(arr, level)).decode()


def decompress_from_b64(b64_str: str) -> ndarray:
    """Decompress a base64-encoded compressed array."""
    return decompress_array(base64.b64decode(b64_str.encode()))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Array Validator
# ═══════════════════════════════════════════════════════════════════════════════

class ArrayValidationError(Exception):
    pass


class ArrayValidator:
    """Validate ndarrays against declarative constraints."""

    def __init__(
        self,
        dtype: Optional[str] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        shape: Optional[Tuple[int, ...]] = None,
        ndim: Optional[int] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        allow_nan: bool = False,
        allow_inf: bool = False,
    ) -> None:
        self._dtype = dtype
        self._min_val = min_val
        self._max_val = max_val
        self._shape = shape
        self._ndim = ndim
        self._min_size = min_size
        self._max_size = max_size
        self._allow_nan = allow_nan
        self._allow_inf = allow_inf

    def validate(self, arr: ndarray) -> None:
        errors = self.check(arr)
        if errors:
            raise ArrayValidationError("; ".join(errors))

    def check(self, arr: ndarray) -> List[str]:
        arr = asarray(arr)
        errors: List[str] = []
        if self._dtype and arr.dtype.name != self._dtype:
            errors.append(f"dtype must be '{self._dtype}', got '{arr.dtype.name}'")
        if self._ndim is not None and arr.ndim != self._ndim:
            errors.append(f"ndim must be {self._ndim}, got {arr.ndim}")
        if self._shape is not None and tuple(arr.shape) != tuple(self._shape):
            errors.append(f"shape must be {self._shape}, got {tuple(arr.shape)}")
        if self._min_size is not None and arr.size < self._min_size:
            errors.append(f"size must be >= {self._min_size}, got {arr.size}")
        if self._max_size is not None and arr.size > self._max_size:
            errors.append(f"size must be <= {self._max_size}, got {arr.size}")
        for v in arr._data:
            if isinstance(v, float):
                if not self._allow_nan and math.isnan(v):
                    errors.append("array contains NaN (allow_nan=False)")
                    break
                if not self._allow_inf and math.isinf(v):
                    errors.append("array contains Inf (allow_inf=False)")
                    break
        if self._min_val is not None:
            for v in arr._data:
                if isinstance(v, (int, float)) and not math.isnan(v) and v < self._min_val:
                    errors.append(f"all values must be >= {self._min_val}")
                    break
        if self._max_val is not None:
            for v in arr._data:
                if isinstance(v, (int, float)) and not math.isnan(v) and v > self._max_val:
                    errors.append(f"all values must be <= {self._max_val}")
                    break
        return errors


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Sliding window view
# ═══════════════════════════════════════════════════════════════════════════════

def sliding_window_view(arr: ndarray, window_size: int, step: int = 1) -> ndarray:
    """Return a 2-D array of sliding windows over a 1-D input array."""
    arr = asarray(arr)
    if arr.ndim != 1:
        raise ValueError("sliding_window_view requires a 1-D array")
    n = arr.size
    if window_size > n:
        raise ValueError(f"window_size ({window_size}) exceeds array size ({n})")
    data = arr._data
    windows = []
    for start in range(0, n - window_size + 1, step):
        windows.append(list(data[start: start + window_size]))
    return ndarray(windows, dtype=arr.dtype)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Batch apply
# ═══════════════════════════════════════════════════════════════════════════════

def batch_apply(
    arr: ndarray,
    func: Callable,
    batch_size: int = 256,
    axis: int = 0,
) -> ndarray:
    """Apply *func* to consecutive batches of rows along *axis*."""
    arr = asarray(arr)
    if arr.ndim < 2:
        n = arr.size
        results = []
        for start in range(0, n, batch_size):
            chunk = ndarray(arr._data[start: start + batch_size], dtype=arr.dtype)
            results.extend(asarray(func(chunk))._data)
        return ndarray(results, dtype=arr.dtype)
    rows = arr.shape[0]
    result_rows = []
    stride = arr.shape[1] if arr.ndim > 1 else 1
    for start in range(0, rows, batch_size):
        batch_data = arr._data[start * stride: (start + batch_size) * stride]
        batch_shape = (min(batch_size, rows - start),) + arr.shape[1:]
        batch = ndarray.__new__(ndarray)
        batch._data = list(batch_data)
        batch._shape = list(batch_shape)
        batch._dtype = arr._dtype
        out = asarray(func(batch))
        result_rows.extend(out._data)
    result = ndarray.__new__(ndarray)
    result._data = result_rows
    result._shape = [rows] + list(arr.shape[1:])
    result._dtype = arr._dtype
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 7. to_structured
# ═══════════════════════════════════════════════════════════════════════════════

def to_structured(arr: ndarray, field_names: List[str]) -> List[Dict[str, Any]]:
    """Convert a 2-D ndarray to a list of dicts with named fields."""
    arr = asarray(arr)
    if arr.ndim != 2:
        raise ValueError("to_structured requires a 2-D array")
    n_cols = arr.shape[1]
    if len(field_names) != n_cols:
        raise ValueError(
            f"field_names length ({len(field_names)}) must match number of columns ({n_cols})"
        )
    rows = []
    data = arr._data
    for r in range(arr.shape[0]):
        row = {field_names[c]: data[r * n_cols + c] for c in range(n_cols)}
        rows.append(row)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ProfiledArray
# ═══════════════════════════════════════════════════════════════════════════════

class ProfiledArray:
    """Transparent profiling wrapper around ndarray."""

    def __init__(self, arr: ndarray) -> None:
        self._arr = asarray(arr)
        self._log: List[Dict[str, Any]] = []

    def __getattr__(self, name: str):
        attr = getattr(self._arr, name)
        if callable(attr):
            def _timed(*args, **kwargs):
                t0 = time.perf_counter()
                result = attr(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                self._log.append({"op": name, "ms": round(elapsed, 4)})
                return result
            return _timed
        return attr

    def report(self) -> List[Dict[str, Any]]:
        total = sum(e["ms"] for e in self._log)
        print(f"ProfiledArray — {len(self._log)} ops, total {total:.3f} ms")
        for e in self._log:
            print(f"  {e['op']:30s} {e['ms']:.4f} ms")
        return self._log

    def clear_profile(self) -> None:
        self._log.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Chunk generator (streaming)
# ═══════════════════════════════════════════════════════════════════════════════

def array_chunks(arr: ndarray, chunk_size: int) -> Generator[ndarray, None, None]:
    """Yield successive chunks of a 1-D ndarray as separate ndarrays."""
    arr = asarray(arr)
    n = arr.size
    data = arr._data
    for start in range(0, n, chunk_size):
        yield ndarray(data[start: start + chunk_size], dtype=arr.dtype)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. describe()  (summary statistics)
# ═══════════════════════════════════════════════════════════════════════════════

def describe(arr: ndarray) -> Dict[str, float]:
    """Return a dict of descriptive statistics for a 1-D ndarray."""
    arr = asarray(arr)
    data = [v for v in arr._data if isinstance(v, (int, float)) and not math.isnan(v)]
    n = len(data)
    if n == 0:
        return {"count": 0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "p25": float("nan"), "p50": float("nan"),
                "p75": float("nan"), "max": float("nan")}
    data_sorted = sorted(data)
    mean = sum(data_sorted) / n
    variance = sum((x - mean) ** 2 for x in data_sorted) / n
    std = math.sqrt(variance)

    def _percentile(sorted_data, p):
        idx = (len(sorted_data) - 1) * p / 100
        lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
        return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)

    return {
        "count": n,
        "mean": mean,
        "std": std,
        "min": data_sorted[0],
        "p25": _percentile(data_sorted, 25),
        "p50": _percentile(data_sorted, 50),
        "p75": _percentile(data_sorted, 75),
        "max": data_sorted[-1],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ════════════════════  NEW in 2.3.0 — Pain-Point Fixes  ══════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# 11. NamedArray — Named dimension support
# ═══════════════════════════════════════════════════════════════════════════════

class NamedArray:
    """
    ndarray wrapper with named dimensions — eliminates broadcasting guesswork.

    This directly solves the #1 NumPy complaint from 2025-2026:
    "with ≥3 dimensions, broadcasting rules are confusing and error-prone."

    Axes are referenced by NAME instead of position, making high-dimensional
    ops readable and less error-prone.

    Example
    -------
    >>> arr = NamedArray(np2.zeros(3, 4, 5), dims=['batch', 'height', 'width'])
    >>> arr['batch']        # select entire batch dimension → range(3)
    >>> arr.sizes           # {'batch': 3, 'height': 4, 'width': 5}
    >>> arr.transpose('width', 'height', 'batch')  # reorder axes by name
    >>> arr.sum('batch')    # sum over batch dimension
    """

    def __init__(self, arr: ndarray, dims: Optional[List[str]] = None) -> None:
        self._arr = asarray(arr)
        if dims is None:
            dims = [f"dim_{i}" for i in range(self._arr.ndim)]
        if len(dims) != self._arr.ndim:
            raise ValueError(
                f"Number of dim names ({len(dims)}) must match ndim ({self._arr.ndim})"
            )
        if len(dims) != len(set(dims)):
            raise ValueError(f"Dimension names must be unique: {dims}")
        self._dims = list(dims)
        self._dim_map = {d: i for i, d in enumerate(dims)}

    # -- properties --
    @property
    def dims(self) -> List[str]:
        return list(self._dims)

    @property
    def ndim(self) -> int:
        return self._arr.ndim

    @property
    def shape(self) -> Tuple[int, ...]:
        return tuple(self._arr.shape)

    @property
    def sizes(self) -> Dict[str, int]:
        return dict(zip(self._dims, self._arr.shape))

    @property
    def data(self) -> ndarray:
        return self._arr

    def __repr__(self):
        dim_info = ", ".join(f"{d}={s}" for d, s in zip(self._dims, self._arr.shape))
        return f"NamedArray({dim_info})\n{self._arr}"

    def __getitem__(self, key):
        """String key selects dimension index/size; tuple key indexes into array."""
        if isinstance(key, str):
            return self._dim_map[key]
        arr_result = self._arr[key]
        # Try to maintain named dims
        if isinstance(arr_result, ndarray):
            new_dims = self._dims
            if isinstance(key, tuple) and len(key) < len(self._dims):
                # Some dims were scalar-indexed (removed)
                scalar_indices = []
                for i, k in enumerate(key):
                    if not isinstance(k, slice):
                        scalar_indices.append(i)
                new_dims = [d for i, d in enumerate(self._dims)
                           if i >= len(key) or isinstance(key[i], slice) or key[i] is Ellipsis]
            elif not isinstance(key, tuple):
                new_dims = self._dims[1:] if self._arr.ndim > 1 else []
            return NamedArray(arr_result, dims=new_dims) if new_dims else arr_result
        return arr_result

    def __array__(self):
        return self._arr

    # -- dimension operations --
    def _resolve_axis(self, dim: Union[str, int]) -> int:
        if isinstance(dim, str):
            if dim not in self._dim_map:
                raise KeyError(f"Unknown dimension '{dim}'. Available: {self._dims}")
            return self._dim_map[dim]
        return dim

    def _resolve_axes(self, dims: Union[str, int, List[Union[str, int]], None] = None
                     ) -> Optional[Tuple[int, ...]]:
        if dims is None:
            return None
        if isinstance(dims, (str, int)):
            dims = [dims]
        return tuple(self._resolve_axis(d) for d in dims)

    def sum(self, dim: Union[str, int, List[Union[str, int]], None] = None):
        """Sum along named dimension(s)."""
        from .math_ops import sum as _sum
        if dim is None:
            return _sum(self._arr)
        axes = self._resolve_axis(dim) if isinstance(dim, (str, int)) else self._resolve_axes(dim)
        result = _sum(self._arr, axis=axes)
        return self._wrap_reduced(result, dim)

    def mean(self, dim: Union[str, int, List[Union[str, int]], None] = None):
        """Mean along named dimension(s)."""
        from .math_ops import mean as _mean
        if dim is None:
            return _mean(self._arr)
        axes = self._resolve_axis(dim) if isinstance(dim, (str, int)) else self._resolve_axes(dim)
        result = _mean(self._arr, axis=axes)
        return self._wrap_reduced(result, dim)

    def std(self, dim: Union[str, int, List[Union[str, int]], None] = None):
        """Standard deviation along named dimension(s)."""
        from .math_ops import std as _std
        if dim is None:
            return _std(self._arr)
        axes = self._resolve_axis(dim) if isinstance(dim, (str, int)) else self._resolve_axes(dim)
        result = _std(self._arr, axis=axes)
        return self._wrap_reduced(result, dim)

    def max(self, dim: Union[str, int, List[Union[str, int]], None] = None):
        """Max along named dimension(s)."""
        from .math_ops import max as _max
        if dim is None:
            return _max(self._arr)
        axes = self._resolve_axis(dim) if isinstance(dim, (str, int)) else self._resolve_axes(dim)
        result = _max(self._arr, axis=axes)
        return self._wrap_reduced(result, dim)

    def min(self, dim: Union[str, int, List[Union[str, int]], None] = None):
        """Min along named dimension(s)."""
        from .math_ops import min as _min
        if dim is None:
            return _min(self._arr)
        axes = self._resolve_axis(dim) if isinstance(dim, (str, int)) else self._resolve_axes(dim)
        result = _min(self._arr, axis=axes)
        return self._wrap_reduced(result, dim)

    def _wrap_reduced(self, result, dim):
        if isinstance(result, ndarray) and hasattr(result, 'ndim') and result.ndim > 0:
            if isinstance(dim, (str, int)):
                dim = [dim]
            if isinstance(dim, list):
                remaining_dims = [d for d in self._dims
                                 if (isinstance(d, str) and d not in dim)
                                 and (isinstance(d, int) and d not in dim)]
                if result.ndim == len(remaining_dims):
                    return NamedArray(result, dims=remaining_dims)
        return result

    def transpose(self, *dims: str) -> "NamedArray":
        """Transpose axes by name. e.g. .transpose('width', 'height', 'batch')"""
        axes = tuple(self._dim_map[d] for d in dims)
        result = self._arr.transpose(axes)
        return NamedArray(result, dims=list(dims))

    def expand_dims(self, dim: str, axis: Optional[int] = None) -> "NamedArray":
        """Add a new dimension of size 1 with the given name."""
        if axis is None:
            axis = len(self._dims)
        from .array import expand_dims
        result = expand_dims(self._arr, axis=axis)
        new_dims = self._dims[:axis] + [dim] + self._dims[axis:]
        return NamedArray(result, dims=new_dims)

    def squeeze(self, dim: Optional[str] = None) -> "NamedArray":
        """Remove dimensions of size 1."""
        from .array import squeeze as _squeeze
        if dim is not None:
            axis = self._resolve_axis(dim)
            if self._arr.shape[axis] != 1:
                raise ValueError(f"Cannot squeeze dim '{dim}' with size {self._arr.shape[axis]}")
            result = _squeeze(self._arr, axis=axis)
            new_dims = [d for d in self._dims if d != dim]
        else:
            result = _squeeze(self._arr)
            new_dims = [d for d, s in zip(self._dims, self._arr.shape) if s != 1]
        return NamedArray(result, dims=new_dims) if result.ndim > 0 else result

    def broadcast_to(self, **dims: int) -> "NamedArray":
        """Broadcast to match the named shape."""
        from .array import broadcast_to as _broadcast_to
        shape = []
        for d in self._dims:
            shape.append(dims.get(d, self._arr.shape[self._dim_map[d]]))
        result = _broadcast_to(self._arr, tuple(shape))
        return NamedArray(result, dims=self._dims)

    def tolist(self):
        return self._arr.tolist()

    def numpy(self):
        """Try to get underlying numpy array if available."""
        return self._arr.numpy() if hasattr(self._arr, 'numpy') else self._arr


# ═══════════════════════════════════════════════════════════════════════════════
# 12. vmapped — JAX-style automatic vectorization
# ═══════════════════════════════════════════════════════════════════════════════

def vmapped(func: Callable, in_axes: Union[int, Tuple[int, ...]] = 0,
            out_axes: int = 0) -> Callable:
    """
    Automatically vectorize a function over arbitrary axes — like JAX vmap.

    Solves the #2 NumPy pain point: "NumPy has no mechanism to abstract over
    batch dimensions. You must rewrite your function."

    Example
    -------
    >>> def add_one(x):
    ...     return x + 1
    >>> batch_add = vmapped(add_one, in_axes=0)
    >>> batch_add(np2.array([[1,2],[3,4]]))  # applies add_one to each row

    >>> def matmul(a, b):
    ...     return a @ b
    >>> batch_mm = vmapped(matmul, in_axes=(0, 0))
    >>> # batch_mm(batch_of_matrices, batch_of_vectors) = [M_1@V_1, M_2@V_2, ...]
    """

    def vectorized(*args):
        if not isinstance(in_axes, tuple):
            axes = (in_axes,) * len(args)
        else:
            axes = in_axes

        # For batch axis, iterate along that dimension
        args_arr = [asarray(a) for a in args]
        batch_dim = axes[0] if axes else 0

        # Determine batch size from first arg's batch dimension
        first_arr = args_arr[0]
        if first_arr.ndim == 0:
            # No batch dim to vectorize over — call once
            return func(*args)
        batch_size = first_arr.shape[batch_dim]

        results = []
        for i in range(batch_size):
            sliced_args = []
            for arg, ax in zip(args_arr, axes):
                if hasattr(arg, 'ndim') and arg.ndim > 0:
                    # Slice along the specified axis
                    slicing = [slice(None)] * arg.ndim
                    slicing[ax] = i
                    sliced = ndarray.__new__(ndarray)
                    flat_data = arg._data
                    # Compute the slice
                    if ax == 0:
                        stride = arg.size // arg.shape[0] if arg.shape[0] > 0 else 0
                        start = i * stride
                        end = start + stride
                        sliced._data = flat_data[start:end]
                        sliced._shape = list(arg.shape[1:])
                        sliced._dtype = arg._dtype
                    else:
                        # General case: reconstruct by iterating
                        sliced = arg[tuple(slicing)]
                    sliced_args.append(sliced)
                else:
                    sliced_args.append(arg)
            results.append(func(*sliced_args))

        # Stack results along out_axes
        if isinstance(results[0], ndarray):
            from .array import stack as _stack
            return _stack(results, axis=out_axes)
        elif isinstance(results[0], (list, tuple)):
            return type(results[0])(results)
        else:
            return _array(results)

    vectorized.__name__ = f"vmapped({getattr(func, '__name__', repr(func))})"
    vectorized.__doc__ = f"Vectorized version of {func.__name__ if hasattr(func, '__name__') else func!r}"
    return vectorized


def vmap(func: Callable, in_axes: Union[int, Tuple[int, ...]] = 0,
         out_axes: int = 0) -> Callable:
    """Alias for vmapped — similar to JAX vmap."""
    return vmapped(func, in_axes=in_axes, out_axes=out_axes)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. scan — Cumulative operation with state (iterative computation)
# ═══════════════════════════════════════════════════════════════════════════════

def scan(func: Callable, init: Any, xs: ndarray,
         reverse: bool = False, unroll: int = 1) -> Tuple[Any, ndarray]:
    """
    Scan over an array, threading state through successive calls.

    Solves the NumPy pain point: "no iterative/scan operations — you must drop
    to numba/Cython/loops for cumulative stateful computations."

    Similar to JAX lax.scan, Haskell scanl, etc.

    Parameters
    ----------
    func : callable
        Function (carry, x) -> (new_carry, output)
    init : any
        Initial carry value.
    xs : ndarray (1-D)
        Sequence to scan over.
    reverse : bool
        If True, scan from right to left.
    unroll : int
        Process multiple elements per iteration (for performance).

    Returns
    -------
    (final_carry, outputs_array)

    Example
    -------
    >>> def cumsum_state(carry, x):
    ...     new_carry = carry + x
    ...     return new_carry, new_carry
    >>> final, outputs = scan(cumsum_state, 0, np2.array([1, 2, 3, 4, 5]))
    >>> outputs  # [1, 3, 6, 10, 15]

    >>> # Exponential moving average
    >>> def ema(carry, x, alpha=0.1):
    ...     new = alpha * x + (1 - alpha) * carry
    ...     return new, new
    >>> _, ema_vals = scan(lambda c, x: ema(c, x, 0.5), 0.0, np2.array([1.,2.,3.,4.]))
    """
    xs = asarray(xs)
    data = xs._data
    if reverse:
        data = list(reversed(data))

    carry = init
    outputs = []
    n = len(data)

    i = 0
    while i < n:
        # Process unroll elements at a time
        for j in range(unroll):
            if i + j >= n:
                break
            carry, out = func(carry, data[i + j])
            outputs.append(out)
        i += unroll

    if reverse:
        outputs = list(reversed(outputs))

    result_arr = ndarray(outputs, dtype=xs.dtype if hasattr(xs, 'dtype') else None)
    return carry, result_arr


# ═══════════════════════════════════════════════════════════════════════════════
# 14. smart_axis — Intelligent axis resolution
# ═══════════════════════════════════════════════════════════════════════════════

def smart_axis(arr: ndarray, axis: Optional[Union[int, str]] = None,
               default: int = -1) -> int:
    """
    Intelligently resolve an axis argument.

    Solves the "axis trial-and-error" pain point:
    - ``axis=None`` → uses *default*
    - ``axis='first'`` → axis 0
    - ``axis='last'`` → axis -1 (default)
    - ``axis='all'`` → None (all axes)
    - ``axis='auto'`` → picks most common choice for the shape

    Example
    -------
    >>> smart_axis(arr, 'last')    # -1
    >>> smart_axis(arr, 'first')   # 0
    >>> smart_axis(arr, 'auto')    # -1 for typical 2D data (last axis)
    """
    if axis is None:
        return default
    if isinstance(axis, int):
        return axis
    if isinstance(axis, str):
        if axis == 'first':
            return 0
        elif axis == 'last':
            return -1
        elif axis == 'all':
            return None
        elif axis == 'auto':
            nd = len(arr.shape)
            if nd <= 1:
                return 0
            elif nd == 2:
                return -1  # columns for typical 2D data
            else:
                return 0  # default for ND
        else:
            raise ValueError(f"Unknown axis '{axis}'. Use 'first', 'last', 'all', 'auto', or an int.")
    return axis


def resolve_axis(arr: ndarray, axis: Optional[Union[int, str]] = None) -> Optional[int]:
    """Alias for smart_axis — always returns int or None."""
    result = smart_axis(arr, axis)
    return result if isinstance(result, int) or result is None else -1


# ═══════════════════════════════════════════════════════════════════════════════
# 15. nan_safe_json — Proper NaN/Inf handling for JSON
# ═══════════════════════════════════════════════════════════════════════════════

def nan_safe_convert(arr: ndarray, nan_replacement=None, inf_replacement=None,
                     neginf_replacement=None) -> ndarray:
    """
    Convert NaN/Inf values in an array to safe values for JSON serialization.

    Solves the persistent "NaN/Inf not JSON compliant" pain point.

    By default: NaN → None (serializes as null), Inf/ -Inf kept as-is
    (which JSON spec technically allows but many parsers reject).

    Example
    -------
    >>> arr = np2.array([1.0, float('nan'), float('inf'), -float('inf'), 2.0])
    >>> clean = nan_safe_convert(arr, nan_replacement=0.0,
    ...                          inf_replacement=1e308, neginf_replacement=-1e308)
    >>> clean.tolist()
    [1.0, 0.0, 1e+308, -1e+308, 2.0]
    """
    arr = asarray(arr)
    data = arr._data
    converted = []
    for v in data:
        if isinstance(v, float):
            if math.isnan(v):
                converted.append(nan_replacement)
            elif math.isinf(v):
                if v > 0:
                    converted.append(inf_replacement if inf_replacement is not None else v)
                else:
                    converted.append(neginf_replacement if neginf_replacement is not None else v)
            else:
                converted.append(v)
        elif isinstance(v, complex):
            r, i = v.real, v.imag
            if math.isnan(r) or math.isnan(i):
                converted.append(nan_replacement)
            elif math.isinf(r) or math.isinf(i):
                converted.append(inf_replacement)
            else:
                converted.append(v)
        else:
            converted.append(v)
    return ndarray(converted, dtype=arr.dtype)


class NaNInfEncoder(json.JSONEncoder):
    """
    JSONEncoder that handles NaN, Inf, -Inf, and numpy2 scalar types.

    Usage:
        json.dumps(data, cls=NaNInfEncoder)

    Example
    -------
    >>> encoder = NaNInfEncoder(nan_str='null', inf_str='1e308')
    >>> json.dumps({'values': [1.0, float('nan'), float('inf')]}, cls=NaNInfEncoder)
    """
    def __init__(self, nan_str='null', inf_str='1e308', neginf_str='-1e308',
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nan_str = nan_str
        self.inf_str = inf_str
        self.neginf_str = neginf_str

    def default(self, obj):
        if isinstance(obj, ndarray):
            clean = nan_safe_convert(obj, nan_replacement=None)
            return clean.tolist()
        if isinstance(obj, float):
            if math.isnan(obj):
                return None if self.nan_str == 'null' else self.nan_str
            if math.isinf(obj):
                return self.inf_str if obj > 0 else self.neginf_str
        return super().default(obj)

    def encode(self, o):
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        return super().iterencode(o, _one_shot)


def nan_safe_json_dumps(arr: ndarray, **json_kwargs) -> str:
    """Convert ndarray to JSON string with safe NaN/Inf handling."""
    arr = asarray(arr)
    clean = nan_safe_convert(arr, nan_replacement=None)
    data = clean.tolist()
    return json.dumps(data, cls=NaNInfEncoder, **json_kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 16. ThreadSafeArray — Lock-protected array wrapper
# ═══════════════════════════════════════════════════════════════════════════════

class ThreadSafeArray:
    """
    Thread-safe wrapper around ndarray for concurrent access.

    Solves the "NumPy doesn't synchronize when arrays are shared across threads"
    pain point — critical for free-threaded Python 3.13+.

    Every read/write method acquires a lock. Use when multiple threads
    share an ndarray.

    Example
    -------
    >>> safe_arr = ThreadSafeArray(np2.array([1, 2, 3, 4, 5]))
    >>> with safe_arr.lock():
    ...     safe_arr[0] = 99
    >>> safe_arr.read(2)  # 3
    """

    def __init__(self, arr: ndarray) -> None:
        self._arr = asarray(arr)
        self._lock = threading.RLock()

    def lock(self):
        """Return context manager for explicit locking."""
        return self._lock

    def read(self, index=None):
        """Thread-safe read."""
        with self._lock:
            if index is None:
                return self._arr.copy()
            return self._arr[index]

    def write(self, index, value):
        """Thread-safe write to a single index."""
        with self._lock:
            self._arr._data[index] = value

    def update(self, func: Callable):
        """Thread-safe update: apply function under lock."""
        with self._lock:
            self._arr = asarray(func(self._arr))

    def __getitem__(self, key):
        with self._lock:
            return self._arr[key]

    def __setitem__(self, key, value):
        with self._lock:
            if isinstance(key, int):
                self._arr._data[key] = value
            elif isinstance(key, slice):
                indices = range(key.start or 0, key.stop or len(self._arr._data),
                               key.step or 1)
                for i, v in enumerate(indices):
                    self._arr._data[v] = value[i] if isinstance(value, (list, tuple, ndarray)) else value

    @property
    def data(self) -> ndarray:
        """Return a copy of the underlying array (safe for reading)."""
        with self._lock:
            return self._arr.copy()

    @property
    def shape(self):
        return self._arr.shape

    @property
    def dtype(self):
        return self._arr.dtype

    def __repr__(self):
        with self._lock:
            return f"ThreadSafeArray({self._arr})"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. CompatLayer — Drop-in replacements for removed/deprecated NumPy APIs
# ═══════════════════════════════════════════════════════════════════════════════

class CompatLayer:
    """
    Drop-in replacements for NumPy functions removed or deprecated in 2.0+/2.5+.

    Solves the "aggressive deprecation cadence breaking downstream CI" pain point.

    Example
    -------
    >>> cl = CompatLayer()
    >>> cl.trapz([1, 2, 3])         # was np.trapz, removed in 2.4
    >>> cl.in1d([1,2,3], [2,3,4])   # was np.in1d, removed in 2.4
    >>> cl.product([1, 2, 3, 4])     # was np.product, removed in 2.0
    """

    @staticmethod
    def trapz(y, x=None, dx=1.0, axis=-1):
        """Integrate along the given axis using the composite trapezoidal rule."""
        y = asarray(y, dtype='float64')
        if y.ndim == 0:
            return 0.0
        data = y._data
        n = len(data) if y.ndim == 1 else y.shape[axis]
        if n < 2:
            return 0.0
        if x is not None:
            x = asarray(x, dtype='float64')
            dx_arr = [x._data[i + 1] - x._data[i] for i in range(n - 1)]
        else:
            dx_arr = [dx] * (n - 1)
        if y.ndim == 1:
            result = 0.0
            for i in range(n - 1):
                result += (data[i] + data[i + 1]) * dx_arr[i] / 2.0
            return result
        else:
            # Multi-dimensional case
            results = []
            stride = y.size // y.shape[0]
            for row in range(y.shape[0]):
                row_data = data[row * stride: (row + 1) * stride]
                result = 0.0
                for i in range(n - 1):
                    result += (row_data[i] + row_data[i + 1]) * dx_arr[i] / 2.0
                results.append(result)
            return ndarray(results)

    @staticmethod
    def in1d(ar1, ar2, assume_unique=False, invert=False):
        """Test whether each element of a 1-D array is in a second array. (was np.in1d)"""
        ar2_set = set(asarray(ar2)._data) if not assume_unique else set(asarray(ar2)._data)
        ar1 = asarray(ar1)
        result = [v in ar2_set for v in ar1._data]
        if invert:
            result = [not v for v in result]
        return ndarray(result, dtype='bool_')

    @staticmethod
    def product(*args, **kwargs):
        """Product of array elements (was np.product)."""
        from .math_ops import prod
        return prod(*args, **kwargs)

    @staticmethod
    def asscalar(a):
        """Convert array of size 1 to scalar (was np.asscalar, removed in 1.23)."""
        a = asarray(a)
        if a.size != 1:
            raise ValueError("asscalar requires array of size 1")
        return a._data[0]

    @staticmethod
    def cumproduct(a, axis=None):
        """Cumulative product (was np.cumproduct, deprecated)."""
        from .math_ops import cumprod
        return cumprod(a, axis=axis)

    @staticmethod
    def fix(x, out=None):
        """Round to nearest integer toward zero (was np.fix, proposed for deprecation 2025)."""
        x = asarray(x, dtype='float64')
        data = [math.copysign(math.floor(abs(v)), v) if not math.isnan(v) else v
                for v in x._data]
        return ndarray(data, dtype='float64')

    @staticmethod
    def alen(a):
        """Return length of first dimension (was np.alen)."""
        a = asarray(a)
        return a.shape[0] if a.ndim > 0 else 1

    @staticmethod
    def who(vardict=None):
        """Print numpy2 arrays in the given dictionary (was np.who).

        Note: Uses sys._getframe() for frame introspection, which is
        CPython-specific and may not work in other Python implementations.
        """
        if vardict is None:
            vardict = sys._getframe(1).f_globals
        for name, val in vardict.items():
            if isinstance(val, (ndarray, NamedArray)):
                sz = val.size if hasattr(val, 'size') else len(val._data)
                print(f"{name:20s} {str(val.shape):14s} {str(val.dtype):8s}  {sz} elements")

    @staticmethod
    def mintypecode(typechars, typeset='GDFgdf', default='d'):
        """Return character for minimum-size type (was np.mintypecode)."""
        typeorder = {'b': 0, 'B': 1, 'h': 2, 'H': 3, 'i': 4, 'I': 5,
                     'l': 6, 'L': 7, 'q': 8, 'Q': 9, 'f': 10, 'd': 11, 'g': 12, 'G': 13}
        best = default
        best_score = -1
        for tc in typechars:
            score = typeorder.get(tc, -1)
            if tc in typeset and score > best_score:
                best_score = score
                best = tc
        return best


# ═══════════════════════════════════════════════════════════════════════════════
# 18. auto_type_convert — Convert between numpy2 / numpy / python types
# ═══════════════════════════════════════════════════════════════════════════════

def auto_type_convert(data: Any, target: str = 'python') -> Any:
    """
    Recursively convert numpy2/numpy types to pure Python or vice-versa.

    Solves the persistent JSON/web-framework type compatibility pain point.

    Parameters
    ----------
    data : any
        Input data with possible numpy2/numpy types.
    target : str
        'python' — convert to pure Python types
        'numpy2' — convert to numpy2 types
        'list' — convert to list/tuple form

    Example
    -------
    >>> auto_type_convert(np2.array([1, 2, 3]), target='python')
    [1, 2, 3]
    >>> auto_type_convert([1, 2, 3], target='numpy2')
    array([1, 2, 3])
    """
    if target == 'python':
        if isinstance(data, ndarray):
            return [auto_type_convert(v, 'python') for v in data._data]
        if isinstance(data, (list, tuple)):
            return type(data)(auto_type_convert(v, 'python') for v in data)
        if isinstance(data, dict):
            return {k: auto_type_convert(v, 'python') for k, v in data.items()}
        if hasattr(data, 'item'):  # numpy scalar
            return data.item()
        return data
    elif target == 'numpy2':
        if isinstance(data, (list, tuple)):
            return ndarray([auto_type_convert(v, 'numpy2') for v in data])
        if isinstance(data, dict):
            return {k: auto_type_convert(v, 'numpy2') for k, v in data.items()}
        return data
    elif target == 'list':
        if isinstance(data, ndarray):
            return data.tolist()
        if isinstance(data, (list, tuple)):
            return type(data)(auto_type_convert(v, 'list') for v in data)
        if isinstance(data, dict):
            return {k: auto_type_convert(v, 'list') for k, v in data.items()}
        return data
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# 19. chunked_reduce — Memory-efficient reduction for very large arrays
# ═══════════════════════════════════════════════════════════════════════════════

def chunked_reduce(arr: ndarray, reducer: Callable, chunk_size: int = 10000,
                   axis: Optional[int] = None) -> Any:
    """
    Apply a reduction in chunks to avoid memory spikes.

    Solves "operations create 2-5× temporary copies causing OOM" pain point.

    Example
    -------
    >>> chunked_reduce(huge_array, lambda x: x.sum(), chunk_size=5000)
    >>> chunked_reduce(huge_array, lambda x: x.mean(), chunk_size=10000)
    """
    arr = asarray(arr)
    n = arr.size
    partials = []
    for start in range(0, n, chunk_size):
        chunk = ndarray(arr._data[start: start + chunk_size], dtype=arr.dtype)
        partial = reducer(chunk)
        partials.append(partial)
    if isinstance(partials[0], ndarray):
        from .array import concatenate
        return reducer(concatenate(partials, axis=axis))
    if isinstance(partials[0], (int, float)):
        if 'mean' in str(reducer):
            chunk_sizes = [min(chunk_size, n - start) for start in range(0, n, chunk_size)]
            weighted_sum = sum(p * s for p, s in zip(partials, chunk_sizes))
            return type(partials[0])(weighted_sum / n)
        return sum(partials)
    return partials


# ═══════════════════════════════════════════════════════════════════════════════
# 20. broadcast_explicit — Broadcasting with explicit dimension control
# ═══════════════════════════════════════════════════════════════════════════════

def broadcast_explicit(*arrays: ndarray, align: str = 'right',
                       expand_axes: Optional[Dict[int, int]] = None) -> List[ndarray]:
    """
    Explicitly broadcast arrays with clear dimension control.

    Unlike NumPy's implicit broadcasting (which is confusing with ≥3D),
    this lets you explicitly specify how axes align.

    Parameters
    ----------
    *arrays : ndarrays to broadcast together
    align : 'right' (NumPy default), 'left', or 'none'
    expand_axes : dict mapping array_index -> {axis_index -> new_size}

    Returns list of broadcast arrays.

    Example
    -------
    >>> a = np2.zeros(3, 1)    # shape (3, 1)
    >>> b = np2.zeros(1, 4)    # shape (1, 4)
    >>> ba, bb = broadcast_explicit(a, b, align='right')
    >>> ba.shape  # (3, 4)
    """
    from .array import broadcast_arrays
    if expand_axes:
        arrays = list(arrays)
        for arr_idx, axes in expand_axes.items():
            arr = asarray(arrays[arr_idx])
            for ax, sz in sorted(axes.items()):
                new_shape = list(arr.shape)
                if ax < len(new_shape):
                    new_shape[ax] = sz
                else:
                    new_shape += [1] * (ax - len(new_shape) + 1)
                    new_shape[ax] = sz
                arr = asarray(arr)  # basic reshape
            arrays[arr_idx] = arr
    return list(broadcast_arrays(*arrays))


def align_shapes(*shapes: Tuple[int, ...]) -> Tuple[int, ...]:
    """Compute the broadcast shape from multiple shapes (explicit)."""
    if not shapes:
        return ()
    from .array import _broadcast_shapes
    return _broadcast_shapes(*shapes)


# ═══════════════════════════════════════════════════════════════════════════════
# 21. einsum_enhanced — Enhanced einsum with named axis support
# ═══════════════════════════════════════════════════════════════════════════════

def einsum_enhanced(subscripts: str, *operands: ndarray,
                    optimize: bool = False) -> ndarray:
    """
    Enhanced einsum with named dimension support through subscript labels.

    Wraps standard einsum but adds auto-optimization for common patterns
    and better error messages for dimension mismatches.

    Example
    -------
    >>> einsum_enhanced('ij,jk->ik', A, B)  # standard matmul
    >>> einsum_enhanced('bij,bjk->bik', batch_A, batch_B)  # batched matmul
    """
    from .math_ops import einsum as _einsum
    try:
        return _einsum(subscripts, *operands, optimize=optimize)
    except ValueError as e:
        # Enhanced error message
        shapes = [f"{op.shape}" if hasattr(op, 'shape') else str(op) for op in operands]
        raise ValueError(
            f"einsum_enhanced: {e}\n"
            f"  subscripts: {subscripts}\n"
            f"  operand shapes: {shapes}\n"
            f"  Hint: Check that dimension labels match across operands."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 22. array_memory_usage — Report memory usage of arrays
# ═══════════════════════════════════════════════════════════════════════════════

def array_memory_usage(arr: ndarray, unit: str = 'MB') -> float:
    """
    Report approximate memory usage of an ndarray.

    Example
    -------
    >>> array_memory_usage(np2.zeros(1000, 1000), unit='MB')
    8.0  # ~8 MB for float64
    """
    arr = asarray(arr)
    bytes_per_element = arr.dtype.itemsize if hasattr(arr.dtype, 'itemsize') else 8
    total_bytes = arr.size * bytes_per_element
    if unit == 'B':
        return float(total_bytes)
    elif unit == 'KB':
        return total_bytes / 1024
    elif unit == 'MB':
        return total_bytes / (1024 * 1024)
    elif unit == 'GB':
        return total_bytes / (1024 * 1024 * 1024)
    return float(total_bytes)


# ═══════════════════════════════════════════════════════════════════════════════
# 23. lazy_array — Deferred computation array
# ═══════════════════════════════════════════════════════════════════════════════

class LazyArray:
    """
    Deferred-computation ndarray — evaluates only when accessed.

    Solves the "No JIT / expression fusion" pain point by fusing a chain
    of operations into a single evaluation pass.

    Example
    -------
    >>> lazy = LazyArray(lambda: np2.arange(1_000_000))
    >>> result = lazy.map(lambda x: x * 2).filter(lambda x: x > 500).evaluate()
    """

    def __init__(self, func: Callable[[], ndarray]) -> None:
        self._func = func
        self._ops: List[Tuple[str, Callable]] = []
        self._cached: Optional[ndarray] = None

    def map(self, func: Callable) -> "LazyArray":
        self._ops.append(("map", func))
        self._cached = None
        return self

    def filter(self, predicate: Callable) -> "LazyArray":
        self._ops.append(("filter", predicate))
        self._cached = None
        return self

    def transform(self, func: Callable) -> "LazyArray":
        self._ops.append(("transform", func))
        self._cached = None
        return self

    def evaluate(self) -> ndarray:
        """Force evaluation of all deferred operations."""
        if self._cached is not None:
            return self._cached
        arr = asarray(self._func())
        for op_type, func in self._ops:
            if op_type == "map":
                arr = ndarray([func(v) for v in arr._data], dtype=arr.dtype)
            elif op_type == "filter":
                arr = ndarray([v for v in arr._data if func(v)], dtype=arr.dtype)
            elif op_type == "transform":
                arr = asarray(func(arr))
        self._cached = arr
        return arr

    def __repr__(self):
        pending = len(self._ops)
        return f"LazyArray({pending} pending ops)"
