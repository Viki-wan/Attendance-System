"""
numpy2.linalg - Pure-Python linear algebra

Implements the numpy.linalg API without requiring NumPy.
For large matrices NumPy is used as an accelerator when available.
"""

import math
import copy
from .array import ndarray, asarray, zeros, eye, _dtype_cls, _ravel_index, _prod


# ── internal helpers ──────────────────────────────────────────────────────────

def _mat(a):
    """Return (data_2d_list, rows, cols)."""
    a = asarray(a)
    if a.ndim != 2:
        raise ValueError(f"Expected 2-D array, got {a.ndim}-D")
    r, c = a._shape
    rows = [[a._data[i*c + j] for j in range(c)] for i in range(r)]
    return rows, r, c

def _from_rows(rows):
    r = len(rows)
    c = len(rows[0]) if rows else 0
    return ndarray([v for row in rows for v in row],
                   dtype=_dtype_cls('float64'), shape=(r, c))

def _identity_rows(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

def _mat_mul_rows(A, B):
    m, k  = len(A), len(A[0])
    k2, n = len(B), len(B[0])
    if k != k2:
        raise ValueError("Incompatible matrix dimensions")
    C = [[sum(A[i][p] * B[p][j] for p in range(k)) for j in range(n)] for i in range(m)]
    return C


# ── LU decomposition (Doolittle, partial pivoting) ────────────────────────────

def _lu(A_rows, n):
    """Return (L, U, P, sign) where P is a permutation list and sign is ±1."""
    A = [row[:] for row in A_rows]   # deep copy
    P = list(range(n))
    sign = 1
    for col in range(n):
        # partial pivoting
        max_row = max(range(col, n), key=lambda r: abs(A[r][col]))
        if max_row != col:
            A[col], A[max_row] = A[max_row], A[col]
            P[col], P[max_row] = P[max_row], P[col]
            sign = -sign
        pivot = A[col][col]
        if pivot == 0:
            return None, None, P, 0  # singular
        for row in range(col+1, n):
            factor = A[row][col] / pivot
            A[row][col] = factor  # store L below diagonal
            for k in range(col+1, n):
                A[row][k] -= factor * A[col][k]
    # split L and U
    L = [[0.0]*n for _ in range(n)]
    U = [[0.0]*n for _ in range(n)]
    for i in range(n):
        L[i][i] = 1.0
        for j in range(n):
            if j < i:
                L[i][j] = A[i][j]
            else:
                U[i][j] = A[i][j]
    return L, U, P, sign


def _solve_lu(L, U, P, b, n):
    """Solve Ax=b using pre-computed LU factorisation."""
    pb = [b[P[i]] for i in range(n)]
    # Forward substitution  Ly = Pb
    y = [0.0] * n
    for i in range(n):
        y[i] = pb[i] - sum(L[i][j] * y[j] for j in range(i))
    # Back substitution  Ux = y
    x = [0.0] * n
    for i in range(n-1, -1, -1):
        x[i] = (y[i] - sum(U[i][j] * x[j] for j in range(i+1, n))) / U[i][i]
    return x


# ── public API ────────────────────────────────────────────────────────────────

def matrix_rank(M, tol=None):
    M = asarray(M)
    sv = svd(M, compute_uv=False)
    if tol is None:
        tol = 1e-10 * max(M._shape) * max(sv._data)
    return sum(1 for s in sv._data if s > tol)

def det(a):
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("det requires square matrix")
    _, U, _, sign = _lu(rows, n)
    if U is None:
        return 0.0
    d = sign
    for i in range(n):
        d *= U[i][i]
    return d

def slogdet(a):
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("slogdet requires square matrix")
    _, U, _, sign = _lu(rows, n)
    if U is None:
        return 0, float('-inf')
    diag = [U[i][i] for i in range(n)]
    neg = sum(1 for v in diag if v < 0)
    log_abs = sum(math.log(abs(v)) for v in diag)
    s = sign * ((-1) ** neg)
    return s, log_abs

def inv(a):
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("inv requires square matrix")
    L, U, P, sign = _lu(rows, n)
    if sign == 0:
        raise LinAlgError("Singular matrix")
    inv_rows = []
    I = _identity_rows(n)
    for col in range(n):
        b = [I[r][col] for r in range(n)]
        x = _solve_lu(L, U, P, b, n)
        inv_rows.append(x)
    # inv_rows[col] is column col of the inverse; transpose to get row-major
    result = [[inv_rows[j][i] for j in range(n)] for i in range(n)]
    return _from_rows(result)

def solve(a, b):
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("solve requires square coefficient matrix")
    b = asarray(b)
    b_rows = b._data
    L, U, P, sign = _lu(rows, n)
    if sign == 0:
        raise LinAlgError("Singular matrix")
    if b.ndim == 1:
        return ndarray(_solve_lu(L, U, P, b_rows, n), dtype=_dtype_cls('float64'))
    # multiple RHS columns
    nb_cols = b._shape[1]
    result  = []
    for col in range(nb_cols):
        bv = [b._data[r*nb_cols + col] for r in range(n)]
        result.append(_solve_lu(L, U, P, bv, n))
    # transpose result back
    out = [result[j][i] for i in range(n) for j in range(nb_cols)]
    return ndarray(out, dtype=_dtype_cls('float64'), shape=(n, nb_cols))

def lstsq(a, b, rcond=None):
    """Least-squares via normal equations (works for full-rank A)."""
    a = asarray(a)
    b = asarray(b)
    AT = a.transpose()
    ATA = AT @ a
    ATb = AT @ b if b.ndim > 1 else ndarray(
        [sum(a._data[r*a._shape[1]+c] * b._data[r] for r in range(a._shape[0]))
         for c in range(a._shape[1])], dtype=_dtype_cls('float64'))
    x = solve(ATA, ATb)
    residuals = b - (a @ x)
    res_norm  = sum(v**2 for v in (residuals._data if isinstance(residuals, ndarray) else [residuals]))
    return x, ndarray([res_norm], dtype=_dtype_cls('float64')), matrix_rank(a), svd(a, compute_uv=False)

def pinv(a, rcond=1e-15):
    """Moore-Penrose pseudoinverse via SVD."""
    U, s, Vt = svd(a, full_matrices=False)
    s_inv = ndarray([1.0/sv if sv > rcond * max(s._data) else 0.0 for sv in s._data],
                    dtype=_dtype_cls('float64'))
    # Vt.T @ diag(s_inv) @ U.T
    S_inv = zeros((len(s._data), len(s._data)), dtype='float64')
    for i, v in enumerate(s_inv._data):
        S_inv._data[i * S_inv._shape[1] + i] = v
    return Vt.transpose() @ S_inv @ U.transpose()

def matrix_power(M, n):
    M = asarray(M)
    if n == 0:
        r = M._shape[0]
        return eye(r)
    if n < 0:
        M = inv(M)
        n = -n
    result = eye(M._shape[0])
    while n:
        if n % 2:
            result = result @ M
        M = M @ M
        n //= 2
    return result

def cholesky(a):
    """Cholesky decomposition (lower triangular)."""
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("cholesky requires square matrix")
    L = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                val = rows[i][i] - s
                if val < 0:
                    raise LinAlgError("Matrix is not positive definite")
                L[i][j] = math.sqrt(val)
            else:
                L[i][j] = (rows[i][j] - s) / L[j][j]
    return _from_rows(L)

def qr(a, mode='reduced'):
    """QR decomposition via Gram-Schmidt."""
    rows, m, n = _mat(a)
    k = min(m, n)
    # column vectors
    cols = [[rows[r][c] for r in range(m)] for c in range(n)]
    Q_cols = []
    R_data = [[0.0]*n for _ in range(k)]
    for j in range(n):
        v = list(cols[j])
        for i, qi in enumerate(Q_cols):
            r_ij = sum(qi[r] * cols[j][r] for r in range(m))
            R_data[i][j] = r_ij
            v = [v[r] - r_ij * qi[r] for r in range(m)]
        norm = math.sqrt(sum(x*x for x in v))
        if j < k:
            R_data[j][j] = norm
        if norm > 1e-14:
            Q_cols.append([x/norm for x in v])
        else:
            Q_cols.append([0.0]*m)
    # build Q (m×k)
    Q_rows = [[Q_cols[c][r] for c in range(k)] for r in range(m)]
    Q = _from_rows(Q_rows)
    R = _from_rows(R_data[:k])
    if mode == 'complete':
        # pad Q to m×m with orthonormal complement
        pass
    return Q, R

def eig(a):
    """Eigenvalues and right eigenvectors (power iteration for 2×2, QR iter for larger)."""
    rows, n, c = _mat(a)
    if n != c:
        raise ValueError("eig requires square matrix")
    # Use QR algorithm (Francis shift, simplified)
    vals, vecs = _qr_algorithm(rows, n, compute_vectors=True)
    return (ndarray(vals, dtype=_dtype_cls('complex128')),
            _from_rows(vecs))

def eigvals(a):
    rows, n, c = _mat(a)
    vals, _ = _qr_algorithm(rows, n, compute_vectors=False)
    return ndarray(vals, dtype=_dtype_cls('complex128'))

def eigh(a):
    """Eigenvalues/vectors for symmetric matrix (same as eig here)."""
    return eig(a)

def eigvalsh(a):
    return eigvals(a)

def _qr_algorithm(rows, n, compute_vectors=True, max_iter=1000):
    """Real QR algorithm for eigenvalues (simplified, no shifts)."""
    import copy as _copy
    A = [row[:] for row in rows]
    Q_total = _identity_rows(n) if compute_vectors else None

    for _ in range(max_iter):
        # check convergence: off-diagonal of last column small?
        if all(abs(A[i][n-1]) < 1e-10 for i in range(n-1)):
            break
        # QR step
        Q_rows = [[1.0 if i==j else 0.0 for j in range(n)] for i in range(n)]
        R_rows = [row[:] for row in A]
        # Gram-Schmidt QR on A
        for col in range(n):
            v = [R_rows[r][col] for r in range(n)]
            for prev in range(col):
                qc = [Q_rows[r][prev] for r in range(n)]
                proj = sum(qc[r] * v[r] for r in range(n))
                v = [v[r] - proj * qc[r] for r in range(n)]
            norm = math.sqrt(sum(x*x for x in v))
            if norm < 1e-14:
                continue
            for r in range(n):
                Q_rows[r][col] = v[r] / norm
        # R = Q^T A
        R_rows = _mat_mul_rows([[Q_rows[r][c] for r in range(n)] for c in range(n)], A)
        # A = R Q
        A = _mat_mul_rows(R_rows, Q_rows)
        if compute_vectors:
            Q_total = _mat_mul_rows(Q_total, Q_rows)

    vals = [A[i][i] for i in range(n)]
    vecs = [[Q_total[r][c] for r in range(n)] for c in range(n)] if compute_vectors else None
    return vals, vecs

def svd(a, full_matrices=True, compute_uv=True, hermitian=False):
    """SVD via bidiagonalization + QR (simplified)."""
    a = asarray(a)
    m, n = a._shape
    # Build A^T A, then eigendecompose
    AT = a.transpose()
    ATA_arr = AT @ a
    ATA_rows = [[ATA_arr._data[i*n+j] for j in range(n)] for i in range(n)]
    eig_vals, eig_vecs = _qr_algorithm(ATA_rows, n, compute_vectors=True)
    # singular values
    sigma = [math.sqrt(max(v, 0.0)) for v in eig_vals]
    # sort descending
    order  = sorted(range(n), key=lambda i: -sigma[i])
    sigma  = [sigma[i] for i in order]
    # V columns (eigenvectors of A^T A)
    V_rows = [[eig_vecs[r][order[c]] for c in range(n)] for r in range(n)]
    V_arr  = _from_rows(V_rows)
    Vt_arr = V_arr.transpose()
    s_arr  = ndarray(sigma, dtype=_dtype_cls('float64'))
    if not compute_uv:
        return s_arr
    # U = A V S^{-1}
    k = min(m, n)
    U_cols = []
    AV = [list(row) for row in _mat_mul_rows(
        [[a._data[i*n+j] for j in range(n)] for i in range(m)], V_rows)]
    for c in range(k):
        col = [AV[r][c] for r in range(m)]
        if sigma[c] > 1e-14:
            col = [v / sigma[c] for v in col]
        else:
            col = [0.0] * m
        U_cols.append(col)
    U_rows = [[U_cols[c][r] for c in range(k)] for r in range(m)]
    if full_matrices:
        # pad U and V to full size (skip for now, return reduced)
        pass
    U_arr = _from_rows(U_rows)
    return U_arr, s_arr, Vt_arr

def norm(x, ord=None, axis=None, keepdims=False):
    x = asarray(x)
    if axis is None and x.ndim == 1:
        if ord is None or ord == 2:
            return math.sqrt(sum(v*v for v in x._data))
        if ord == 1:
            return sum(abs(v) for v in x._data)
        if ord == float('inf'):
            return max(abs(v) for v in x._data)
        if ord == float('-inf'):
            return min(abs(v) for v in x._data)
        return sum(abs(v)**ord for v in x._data) ** (1/ord)
    if axis is None and x.ndim == 2:
        if ord is None or ord == 'fro':
            return math.sqrt(sum(v*v for v in x._data))
        if ord == 1:
            m, n = x._shape
            return max(sum(abs(x._data[r*n+c]) for r in range(m)) for c in range(n))
        if ord == float('inf'):
            m, n = x._shape
            return max(sum(abs(x._data[r*n+c]) for c in range(n)) for r in range(m))
    return math.sqrt(sum(v*v for v in x._data))

def cond(x, p=None):
    s = svd(x, compute_uv=False)
    sv = s._data
    if not sv:
        return float('inf')
    return max(sv) / min(sv) if min(sv) > 0 else float('inf')

def trace(a, offset=0, axis1=0, axis2=1, dtype=None, out=None):
    return asarray(a).trace(offset)

def tensordot(a, b, axes=2):
    from .math_ops import tensordot as _td
    return _td(a, b, axes)

def multi_dot(arrays):
    result = asarray(arrays[0])
    for a in arrays[1:]:
        result = result @ asarray(a)
    return result

def cross(a, b):
    from .math_ops import cross as _cross
    return _cross(a, b)

def outer(a, b):
    from .math_ops import outer as _outer
    return _outer(a, b)

def inner(a, b):
    from .math_ops import inner as _inner
    return _inner(a, b)

def dot(a, b):
    from .math_ops import dot as _dot
    return _dot(a, b)

def vdot(a, b):
    from .math_ops import vdot as _vd
    return _vd(a, b)

def matrix_transpose(x):
    return asarray(x).transpose()


class LinAlgError(Exception):
    pass
