"""
numpy2.converters - Data type conversion utilities

No NumPy import required. Handles numpy2 ndarrays, pandas DataFrames,
and plain Python types.
"""

import math
from typing import Any, Dict, List, Union, Optional

from .array import ndarray as _ndarray, asarray
from .dtypes import dtype as _dtype_cls, _normalise

# ── optional pandas ───────────────────────────────────────────────────────────
try:
    import pandas as _pd
    _HAS_PANDAS = True
except ImportError:
    _pd = None
    _HAS_PANDAS = False

# ── optional numpy (interop only) ────────────────────────────────────────────
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _np = None
    _HAS_NUMPY = False


def numpy_to_python(obj: Any) -> Any:
    """
    Convert numpy2 / NumPy types to native Python types.

    Example:
        >>> import numpy2 as np2
        >>> val = np2.int64(42)   # or np2.array([42])[0]
        >>> np2.numpy_to_python(val)
        42
    """
    if isinstance(obj, _ndarray):
        return obj.tolist()

    if _HAS_NUMPY:
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.floating):
            if _np.isnan(obj) or _np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, _np.bool_):
            return bool(obj)
        if isinstance(obj, _np.datetime64):
            return str(obj)
        if isinstance(obj, _np.generic):
            return obj.item()

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, (list, tuple)):
        return type(obj)(numpy_to_python(item) for item in obj)
    if isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}

    return obj


def pandas_to_json(
    df: Any,
    orient: str = 'records',
    include_index: bool = False
) -> Any:
    """
    Convert a pandas DataFrame to a JSON-safe structure.

    Example:
        >>> import pandas as pd
        >>> import numpy2 as np2
        >>> df = pd.DataFrame({'A': [1, 2], 'B': [3.5, 4.5]})
        >>> np2.pandas_to_json(df)
        [{'A': 1, 'B': 3.5}, {'A': 2, 'B': 4.5}]
    """
    if not _HAS_PANDAS:
        raise ImportError("pandas is not installed")
    if not isinstance(df, _pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    df_converted = df.copy()
    for col in df_converted.columns:
        dtype_str = str(df_converted[col].dtype)
        if 'int' in dtype_str or 'float' in dtype_str:
            df_converted[col] = df_converted[col].apply(numpy_to_python)

    result = df_converted.to_dict(orient=orient)

    if include_index and orient == 'records':
        result = [{**row, '__index__': idx} for idx, row in enumerate(result)]

    return result


def python_to_numpy(data: Any, dtype: Optional[str] = None) -> _ndarray:
    """
    Convert Python data to a numpy2 ndarray.

    Example:
        >>> import numpy2 as np2
        >>> np2.python_to_numpy([1, 2, 3], dtype='float32')
        array([1.0, 2.0, 3.0], dtype=float32)
    """
    return _ndarray(data, dtype=dtype)


def infer_dtype(data: Any) -> str:
    """
    Infer an appropriate numpy2 dtype string from Python data.

    Example:
        >>> import numpy2 as np2
        >>> np2.infer_dtype([1, 2, 3])
        'int64'
    """
    if isinstance(data, _ndarray):
        return data.dtype.name

    if _HAS_NUMPY and isinstance(data, _np.ndarray):
        return str(data.dtype)

    if isinstance(data, (list, tuple)):
        if not data:
            return 'float64'
        first = data[0]
        if isinstance(first, bool):
            return 'bool'
        if isinstance(first, int):
            values = [x for x in data if isinstance(x, int)]
            if all(-128 <= v < 128 for v in values):
                return 'int8'
            if all(-32768 <= v < 32768 for v in values):
                return 'int16'
            if all(-2147483648 <= v < 2147483648 for v in values):
                return 'int32'
            return 'int64'
        if isinstance(first, float):
            return 'float64'
        if isinstance(first, complex):
            return 'complex128'
        if isinstance(first, str):
            return 'object'
        if isinstance(first, (list, tuple)):
            return infer_dtype(first)

    if isinstance(data, dict):
        return 'object'

    return 'object'


def safe_cast(
    value: Any,
    target_dtype: str,
    raise_on_error: bool = False
) -> Any:
    """
    Safely cast a value to a target dtype.

    Example:
        >>> import numpy2 as np2
        >>> np2.safe_cast("123", 'int32')
        123
    """
    try:
        dt = _dtype_cls(target_dtype)
        return dt.cast(value)
    except (ValueError, TypeError) as e:
        if raise_on_error:
            raise
        return value


def batch_convert(
    data: List[Dict[str, Any]],
    dtype_map: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Convert a list of records with consistent type handling.

    Example:
        >>> import numpy2 as np2
        >>> data = [{'id': 1, 'value': 3.14}]
        >>> np2.batch_convert(data, {'id': 'int32', 'value': 'float32'})
        [{'id': 1, 'value': 3.14}]
    """
    if dtype_map is None:
        dtype_map = {}

    converted = []
    for record in data:
        new_record = {}
        for key, value in record.items():
            target_dtype = dtype_map.get(key)
            if target_dtype:
                new_record[key] = safe_cast(value, target_dtype)
            else:
                new_record[key] = numpy_to_python(value)
        converted.append(new_record)

    return converted
