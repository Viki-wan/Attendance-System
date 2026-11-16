"""
numpy2.core - Serialization and type conversion utilities

Solves NumPy/pandas JSON serialization issues.
No NumPy import required — works with numpy2's own ndarray.
"""

import json
import math
import sys
from typing import Any, Dict, List, Union, Optional

from .array import ndarray as _ndarray, asarray

# Default maximum size for JSON inputs (50 MB) to prevent resource exhaustion.
_DEFAULT_MAX_JSON_SIZE = 50 * 1024 * 1024


# ── optional pandas ───────────────────────────────────────────────────────────
try:
    import pandas as _pd
    _HAS_PANDAS = True
except ImportError:
    _pd = None
    _HAS_PANDAS = False

# ── optional numpy (for interop only) ────────────────────────────────────────
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _np = None
    _HAS_NUMPY = False


# ── JSON encoder ──────────────────────────────────────────────────────────────

class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles numpy2 ndarrays, NumPy types (if installed),
    and pandas objects (if installed).

    Example:
        >>> import json
        >>> import numpy2 as np2
        >>> arr = np2.array([1, 2, 3])
        >>> json.dumps(arr, cls=np2.JSONEncoder)
        '[1, 2, 3]'
    """

    def default(self, obj: Any) -> Any:
        # numpy2 ndarray
        if isinstance(obj, _ndarray):
            # convert NaN/Inf to None so json.dumps produces valid JSON
            def _safe(v):
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
                if isinstance(v, list):
                    return [_safe(x) for x in v]
                return v
            return _safe(obj.tolist())

        # numpy2 scalar wrappers (int, float, complex subclasses)
        if isinstance(obj, complex):
            if math.isnan(obj.real) or math.isnan(obj.imag):
                return None
            return {"real": obj.real, "imag": obj.imag}

        # pandas objects
        if _HAS_PANDAS:
            if isinstance(obj, _pd.DataFrame):
                return obj.to_dict(orient='records')
            if isinstance(obj, _pd.Series):
                return obj.to_dict()
            if isinstance(obj, _pd.Index):
                return obj.tolist()

        # NumPy objects (when NumPy installed — for interop)
        if _HAS_NUMPY:
            if isinstance(obj, _np.integer):
                return int(obj)
            if isinstance(obj, _np.floating):
                if _np.isnan(obj) or _np.isinf(obj):
                    return None
                return float(obj)
            if isinstance(obj, _np.ndarray):
                return obj.tolist()
            if isinstance(obj, _np.generic):
                return obj.item()
            if isinstance(obj, _np.datetime64):
                return str(obj)
            if isinstance(obj, _np.timedelta64):
                return str(obj)

        # Python float special values
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj

        return super().default(obj)


class JSONDecoder(json.JSONDecoder):
    """
    Custom JSON decoder that reconstructs numpy2 ndarrays from JSON.

    Example:
        >>> import numpy2 as np2
        >>> arr = np2.from_json('[1, 2, 3]', to_numpy=True)
        >>> type(arr)
        <class 'numpy2.array.ndarray'>
    """

    def __init__(self, to_numpy: bool = False, dtype: Optional[str] = None, *args, **kwargs):
        self.to_numpy = to_numpy
        self.dtype = dtype
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj: Dict) -> Any:
        if self.to_numpy and isinstance(obj, dict) and "real" in obj and "imag" in obj:
            return complex(obj["real"], obj["imag"])
        return obj


# ── public API ────────────────────────────────────────────────────────────────

def to_json(obj: Any, indent: Optional[int] = None, **kwargs) -> str:
    """
    Convert numpy2 arrays and pandas objects to JSON string.

    Example:
        >>> import numpy2 as np2
        >>> arr = np2.array([1, 2, 3])
        >>> np2.to_json(arr)
        '[1, 2, 3]'
    """
    return json.dumps(obj, cls=JSONEncoder, indent=indent, **kwargs)


def from_json(
    json_str: str,
    to_numpy: bool = False,
    dtype: Optional[str] = None,
    max_size: Optional[int] = None
) -> Any:
    """
    Deserialize JSON string (optionally to numpy2 ndarray).

    Parameters
    ----------
    json_str : str
        JSON string to deserialize.
    to_numpy : bool
        If True, convert lists to numpy2 ndarray.
    dtype : str or None
        Target dtype for ndarray conversion.
    max_size : int or None
        Maximum allowed size of JSON input in bytes.
        Defaults to 50 MB. Set to None to disable.

    Example:
        >>> import numpy2 as np2
        >>> np2.from_json('[1, 2, 3]', to_numpy=True)
        array([1, 2, 3], dtype=int64)
    """
    limit = max_size if max_size is not None else _DEFAULT_MAX_JSON_SIZE
    if limit is not None and sys.getsizeof(json_str) > limit:
        raise ValueError(
            f"JSON input size ({sys.getsizeof(json_str)} bytes) exceeds "
            f"maximum allowed size ({limit} bytes). "
            "Increase max_size if needed."
        )

    decoder = JSONDecoder(to_numpy=to_numpy, dtype=dtype)
    result = decoder.decode(json_str)

    if to_numpy and isinstance(result, list):
        result = _ndarray(result, dtype=dtype)

    return result


def _to_python_value(v: Any) -> Any:
    """Recursively convert a value to a JSON-safe Python native type."""
    if isinstance(v, _ndarray):
        return v.tolist()
    if _HAS_NUMPY:
        if isinstance(v, _np.integer):
            return int(v)
        if isinstance(v, _np.floating):
            return None if (_np.isnan(v) or _np.isinf(v)) else float(v)
        if isinstance(v, _np.ndarray):
            return v.tolist()
        if isinstance(v, _np.generic):
            return v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: _to_python_value(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return type(v)(_to_python_value(x) for x in v)
    return v


def serialize(obj: Any, include_metadata: bool = False) -> Dict[str, Any]:
    """
    Serialize numpy2 arrays / pandas objects to a JSON-safe dictionary.

    Example:
        >>> import numpy2 as np2
        >>> arr = np2.array([1, 2, 3])
        >>> np2.serialize(arr)
        {'data': [1, 2, 3]}
    """
    if isinstance(obj, _ndarray):
        result: Dict[str, Any] = {'data': obj.tolist()}
        if include_metadata:
            result.update({
                'shape': list(obj.shape),
                'dtype': obj.dtype.name,
                'size':  obj.size,
                'ndim':  obj.ndim,
            })
        return result

    if _HAS_NUMPY and isinstance(obj, _np.ndarray):
        result = {'data': obj.tolist()}
        if include_metadata:
            result.update({
                'shape': list(obj.shape),
                'dtype': str(obj.dtype),
                'size':  int(obj.size),
                'ndim':  int(obj.ndim),
            })
        return result

    if _HAS_PANDAS:
        if isinstance(obj, _pd.DataFrame):
            result = {'data': obj.to_dict(orient='records')}
            if include_metadata:
                result.update({
                    'shape':   list(obj.shape),
                    'columns': list(obj.columns),
                    'index':   obj.index.tolist(),
                })
            return result
        if isinstance(obj, _pd.Series):
            result = {'data': obj.to_dict()}
            if include_metadata:
                result.update({
                    'name':  obj.name,
                    'dtype': str(obj.dtype),
                    'index': obj.index.tolist(),
                })
            return result

    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(v, _ndarray):
                out[k] = v.tolist()
            elif _HAS_NUMPY and isinstance(v, _np.ndarray):
                out[k] = v.tolist()
            elif _HAS_PANDAS and isinstance(v, _pd.Series):
                out[k] = v.to_dict()
            elif _HAS_PANDAS and isinstance(v, _pd.DataFrame):
                out[k] = v.to_dict(orient='records')
            elif isinstance(v, (dict, list, tuple)):
                out[k] = serialize(v, include_metadata)
            else:
                out[k] = _to_python_value(v)
        return out

    if isinstance(obj, (list, tuple)):
        result_list = []
        for item in obj:
            if isinstance(item, _ndarray):
                result_list.append(item.tolist())
            elif _HAS_NUMPY and isinstance(item, _np.ndarray):
                result_list.append(item.tolist())
            elif isinstance(item, (dict, list, tuple)):
                result_list.append(serialize(item, include_metadata))
            else:
                result_list.append(_to_python_value(item))
        return result_list  # type: ignore[return-value]

    return json.loads(json.dumps(obj, cls=JSONEncoder))


def deserialize(
    data: Dict[str, Any],
    to_numpy: bool = True,
    dtype: Optional[str] = None
) -> Any:
    """
    Reconstruct a numpy2 ndarray from a serialized dictionary.

    Example:
        >>> import numpy2 as np2
        >>> np2.deserialize({'data': [1, 2, 3]})
        array([1, 2, 3], dtype=int64)
    """
    if not isinstance(data, dict):
        return data
    if 'data' not in data:
        return data

    array_data = data['data']

    if to_numpy:
        target_dtype = dtype or data.get('dtype', None)
        return _ndarray(array_data, dtype=target_dtype)

    return array_data


def array(data: Any, dtype: Optional[str] = None, **kwargs) -> _ndarray:
    """
    Create a numpy2 ndarray — drop-in for numpy.array().

    Example:
        >>> import numpy2 as np2
        >>> np2.array([1, 2, 3], dtype='int32')
        array([1, 2, 3], dtype=int32)
    """
    return _ndarray(data, dtype=dtype)


class ndarray(_ndarray):
    """
    Web-enabled numpy2 ndarray wrapper.

    Adds convenience methods for serialization.
    """

    def to_json(self, indent: Optional[int] = None) -> str:
        return to_json(self, indent=indent)

    def to_dict(self, include_metadata: bool = False) -> Dict:
        return serialize(self, include_metadata=include_metadata)

    @property
    def numpy(self):
        """Return underlying data as a numpy2 ndarray (self)."""
        return self

    def __repr__(self):
        return f"numpy2.ndarray({self.tolist()!r}, dtype={self.dtype})"
