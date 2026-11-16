"""
numpy2.fft - Pure-Python FFT

Implements the Cooley-Tukey FFT algorithm without NumPy.
"""

import math
import cmath
from .array import ndarray, asarray, _dtype_cls


def _fft_core(x, inverse=False):
    """Cooley-Tukey radix-2 FFT (in-place on list of complex)."""
    n = len(x)
    if n <= 1:
        return x
    # Pad to next power of 2
    m = 1
    while m < n:
        m <<= 1
    if m != n:
        x = x + [0.0+0.0j] * (m - n)
        n = m

    # Bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            x[i], x[j] = x[j], x[i]

    # FFT butterfly
    length = 2
    while length <= n:
        half = length // 2
        angle = 2 * math.pi / length * (1 if inverse else -1)
        w_n   = cmath.exp(1j * angle)
        for i in range(0, n, length):
            w = 1.0 + 0.0j
            for k in range(half):
                u = x[i + k]
                v = x[i + k + half] * w
                x[i + k]        = u + v
                x[i + k + half] = u - v
                w *= w_n
        length <<= 1

    if inverse:
        x = [v / n for v in x]
    return x


def _to_complex_list(a):
    a = asarray(a)
    return [complex(v) for v in a._data]


def fft(a, n=None, axis=-1, norm=None):
    a = asarray(a)
    x = _to_complex_list(a)
    if n is not None:
        if n > len(x):
            x += [0.0+0.0j] * (n - len(x))
        else:
            x = x[:n]
    result = _fft_core(x)
    return ndarray(result, dtype=_dtype_cls('complex128'))


def ifft(a, n=None, axis=-1, norm=None):
    a = asarray(a)
    x = _to_complex_list(a)
    if n is not None:
        if n > len(x):
            x += [0.0+0.0j] * (n - len(x))
        else:
            x = x[:n]
    result = _fft_core(x, inverse=True)
    return ndarray(result, dtype=_dtype_cls('complex128'))


def rfft(a, n=None, axis=-1, norm=None):
    """Real FFT — returns only first n//2+1 frequencies."""
    a = asarray(a)
    x = [float(v) + 0.0j for v in a._data]
    if n is not None:
        if n > len(x):
            x += [0.0+0.0j] * (n - len(x))
        else:
            x = x[:n]
    full = _fft_core(x)
    half = len(full) // 2 + 1
    return ndarray(full[:half], dtype=_dtype_cls('complex128'))


def irfft(a, n=None, axis=-1, norm=None):
    """Inverse real FFT."""
    a = asarray(a)
    x = [complex(v) for v in a._data]
    if n is None:
        n = 2 * (len(x) - 1)
    # reconstruct full spectrum
    full = x + [x[-1-i].conjugate() for i in range(1, n - len(x) + 1)]
    result = _fft_core(full[:n], inverse=True)
    return ndarray([v.real for v in result], dtype=_dtype_cls('float64'))


def hfft(a, n=None, axis=-1, norm=None):
    """FFT of a Hermitian signal."""
    a = asarray(a)
    x = [complex(v) for v in a._data]
    if n is None:
        n = 2 * (len(x) - 1)
    full = [v.conjugate() for v in x[:n//2+1]]
    result = _fft_core(full, inverse=False)
    return ndarray([v.real for v in result], dtype=_dtype_cls('float64'))


def ihfft(a, n=None, axis=-1, norm=None):
    return rfft(a, n=n)


def fft2(a, s=None, axes=(-2, -1), norm=None):
    """2-D FFT via row-then-column 1-D FFTs."""
    a = asarray(a)
    if a.ndim != 2:
        raise ValueError("fft2 requires 2-D array")
    rows, cols = a._shape
    # FFT each row
    row_out = []
    for r in range(rows):
        row = [complex(a._data[r*cols + c]) for c in range(cols)]
        row_out.append(_fft_core(row))
    # FFT each column
    out = [[0.0+0.0j]*cols for _ in range(rows)]
    for c in range(cols):
        col = [row_out[r][c] for r in range(rows)]
        col_result = _fft_core(col)
        for r in range(rows):
            out[r][c] = col_result[r]
    flat = [v for row in out for v in row]
    return ndarray(flat, dtype=_dtype_cls('complex128'), shape=(rows, cols))


def ifft2(a, s=None, axes=(-2, -1), norm=None):
    a = asarray(a)
    if a.ndim != 2:
        raise ValueError("ifft2 requires 2-D array")
    rows, cols = a._shape
    row_out = []
    for r in range(rows):
        row = [complex(a._data[r*cols + c]) for c in range(cols)]
        row_out.append(_fft_core(row, inverse=True))
    out = [[0.0+0.0j]*cols for _ in range(rows)]
    for c in range(cols):
        col = [row_out[r][c] for r in range(rows)]
        col_result = _fft_core(col, inverse=True)
        for r in range(rows):
            out[r][c] = col_result[r]
    flat = [v for row in out for v in row]
    return ndarray(flat, dtype=_dtype_cls('complex128'), shape=(rows, cols))


def fftn(a, s=None, axes=None, norm=None):
    a = asarray(a)
    if a.ndim == 1:
        return fft(a, n=s[0] if s else None)
    if a.ndim == 2:
        return fft2(a, s=s)
    raise NotImplementedError("fftn for ndim>2 not yet implemented in pure mode")


def ifftn(a, s=None, axes=None, norm=None):
    a = asarray(a)
    if a.ndim == 1:
        return ifft(a, n=s[0] if s else None)
    if a.ndim == 2:
        return ifft2(a, s=s)
    raise NotImplementedError("ifftn for ndim>2 not yet implemented in pure mode")


def rfftn(a, s=None, axes=None, norm=None):
    a = asarray(a)
    if a.ndim == 1:
        return rfft(a, n=s[0] if s else None)
    raise NotImplementedError("rfftn for ndim>1 not yet implemented in pure mode")


def irfftn(a, s=None, axes=None, norm=None):
    a = asarray(a)
    if a.ndim == 1:
        return irfft(a, n=s[0] if s else None)
    raise NotImplementedError("irfftn for ndim>1 not yet implemented in pure mode")


def fftshift(x, axes=None):
    x = asarray(x)
    n = len(x._data)
    shift = n // 2
    data = x._data[shift:] + x._data[:shift]
    return ndarray(data, dtype=x.dtype, shape=x._shape)


def ifftshift(x, axes=None):
    x = asarray(x)
    n = len(x._data)
    shift = (n + 1) // 2
    data = x._data[shift:] + x._data[:shift]
    return ndarray(data, dtype=x.dtype, shape=x._shape)


def fftfreq(n, d=1.0):
    if n % 2 == 0:
        freqs = list(range(n//2)) + list(range(-n//2, 0))
    else:
        freqs = list(range((n-1)//2 + 1)) + list(range(-(n-1)//2, 0))
    return ndarray([f / (d * n) for f in freqs], dtype=_dtype_cls('float64'))


def rfftfreq(n, d=1.0):
    freqs = list(range(n//2 + 1))
    return ndarray([f / (d * n) for f in freqs], dtype=_dtype_cls('float64'))
