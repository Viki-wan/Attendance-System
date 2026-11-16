"""
numpy2.dtypes - Pure-Python dtype system

Mirrors NumPy's dtype names and behaviour without depending on NumPy.
"""

import struct
import math

# ── dtype registry ────────────────────────────────────────────────────────────

_DTYPE_INFO = {
    # name          : (kind, itemsize, py_type,  struct_fmt)
    'bool'          : ('b', 1,  bool,  '?'),
    'bool_'         : ('b', 1,  bool,  '?'),
    'int8'          : ('i', 1,  int,   'b'),
    'int16'         : ('i', 2,  int,   'h'),
    'int32'         : ('i', 4,  int,   'i'),
    'int64'         : ('i', 8,  int,   'q'),
    'uint8'         : ('u', 1,  int,   'B'),
    'uint16'        : ('u', 2,  int,   'H'),
    'uint32'        : ('u', 4,  int,   'I'),
    'uint64'        : ('u', 8,  int,   'Q'),
    'float16'       : ('f', 2,  float, 'e'),
    'float32'       : ('f', 4,  float, 'f'),
    'float64'       : ('f', 8,  float, 'd'),
    'float128'      : ('f', 16, float, 'd'),   # stored as float64
    'complex64'     : ('c', 8,  complex, None),
    'complex128'    : ('c', 16, complex, None),
    'object'        : ('O', 8,  object, None),
    'object_'       : ('O', 8,  object, None),
    'str'           : ('U', 8,  str,   None),
    'str_'          : ('U', 8,  str,   None),
    'unicode_'      : ('U', 8,  str,   None),
    'bytes_'        : ('S', 8,  bytes, None),
    'void'          : ('V', 0,  None,  None),
}

# aliases
_ALIASES = {
    'int'     : 'int64',
    'float'   : 'float64',
    'complex' : 'complex128',
    'bool'    : 'bool',
    'double'  : 'float64',
    'single'  : 'float32',
    'half'    : 'float16',
    'longlong': 'int64',
    'ulonglong': 'uint64',
    'short'   : 'int16',
    'ushort'  : 'uint16',
    'byte'    : 'int8',
    'ubyte'   : 'uint8',
    'intp'    : 'int64',
    'int_'    : 'int64',
    'uint'    : 'uint64',
    'float_'  : 'float64',
    'longdouble': 'float64',
}

# Python type → default dtype
_PY_TYPE_MAP = {
    bool    : 'bool',
    int     : 'int64',
    float   : 'float64',
    complex : 'complex128',
    str     : 'str_',
    bytes   : 'bytes_',
}


def _normalise(name):
    """Return canonical dtype name string."""
    if isinstance(name, dtype):
        return name.name
    if name is None:
        return 'float64'
    if isinstance(name, type):
        return _PY_TYPE_MAP.get(name, 'object')
    s = str(name).strip().lower()
    s = _ALIASES.get(s, s)
    if s not in _DTYPE_INFO:
        # handle numpy-style '<f8', '>i4' etc.
        if len(s) >= 2 and s[0] in '<>=|':
            s = s[1:]
        # map char+size  e.g. 'f8' -> float64, 'i4' -> int32
        _char_map = {'b1':'bool','i1':'int8','i2':'int16','i4':'int32','i8':'int64',
                     'u1':'uint8','u2':'uint16','u4':'uint32','u8':'uint64',
                     'f2':'float16','f4':'float32','f8':'float64',
                     'c8':'complex64','c16':'complex128'}
        s = _char_map.get(s, s)
    return s if s in _DTYPE_INFO else 'object'


class dtype:
    """Lightweight dtype descriptor (mirrors numpy.dtype)."""

    __slots__ = ('name', 'kind', 'itemsize', 'py_type', '_fmt')

    def __init__(self, spec=None):
        name = _normalise(spec)
        info = _DTYPE_INFO.get(name, _DTYPE_INFO['object'])
        self.name    = name
        self.kind    = info[0]
        self.itemsize = info[1]
        self.py_type = info[2]
        self._fmt    = info[3]

    # ── coerce a value to this dtype ─────────────────────────────────────────
    def cast(self, value):
        try:
            if self.kind == 'b':
                return bool(value)
            if self.kind in ('i', 'u'):
                if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                    return 0
                return int(value)
            if self.kind == 'f':
                return float(value)
            if self.kind == 'c':
                return complex(value)
            if self.kind == 'U':
                return str(value)
            if self.kind == 'S':
                return bytes(value) if isinstance(value, (bytes, bytearray)) else str(value).encode()
            return value
        except (ValueError, TypeError):
            return value

    def __repr__(self):
        return f"dtype('{self.name}')"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, dtype):
            return self.name == other.name
        return self.name == _normalise(other)

    def __hash__(self):
        return hash(self.name)


# ── module-level dtype singletons (numpy-compatible names) ───────────────────
bool_       = dtype('bool')
int8        = dtype('int8')
int16       = dtype('int16')
int32       = dtype('int32')
int64       = dtype('int64')
int_        = dtype('int64')
intp        = dtype('int64')
intc        = dtype('int32')
uint8       = dtype('uint8')
uint16      = dtype('uint16')
uint32      = dtype('uint32')
uint64      = dtype('uint64')
float16     = dtype('float16')
float32     = dtype('float32')
float64     = dtype('float64')
float_      = dtype('float64')
double      = dtype('float64')
single      = dtype('float32')
half        = dtype('float16')
complex64   = dtype('complex64')
complex128  = dtype('complex128')
object_     = dtype('object')
str_        = dtype('str_')
bytes_      = dtype('bytes_')
longdouble  = dtype('float64')
clongdouble = dtype('complex128')
bool8       = bool_


def result_type(*arrays_and_dtypes):
    """Return the dtype that results from broadcasting these inputs (simplified)."""
    order = ['bool','uint8','int8','uint16','int16','uint32','int32',
             'uint64','int64','float16','float32','float64','complex64','complex128','object']
    best = 'bool'
    for a in arrays_and_dtypes:
        if hasattr(a, 'dtype'):
            n = a.dtype.name
        else:
            n = _normalise(a)
        if n in order and order.index(n) > order.index(best):
            best = n
    return dtype(best)


def _infer_dtype_from_data(data):
    """Infer dtype by scanning a flat iterable of Python values."""
    has_complex = has_float = has_int = has_bool = False
    has_str = has_bytes = False
    for v in data:
        if isinstance(v, bool):
            has_bool = True
        elif isinstance(v, int):
            has_int = True
        elif isinstance(v, float):
            has_float = True
        elif isinstance(v, complex):
            has_complex = True
        elif isinstance(v, str):
            has_str = True
        elif isinstance(v, (bytes, bytearray)):
            has_bytes = True
    if has_str:
        return dtype('str_')
    if has_bytes:
        return dtype('bytes_')
    if has_complex:
        return dtype('complex128')
    if has_float:
        return dtype('float64')
    if has_int:
        return dtype('int64')
    if has_bool:
        return dtype('bool')
    return dtype('float64')
