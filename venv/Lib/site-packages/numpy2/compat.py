"""Compatibility reporting utilities for numpy2.

This module is intentionally lightweight and import-safe. It avoids importing
the top-level ``numpy2`` package to prevent circular imports.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class _NotImplementedSite:
    qualified_name: str
    message: Optional[str]
    filepath: str
    line: int
    kind: str  # "stubbed" | "partial" | "high_risk"


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _read_init_version() -> Optional[str]:
    init_path = _package_root() / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    try:
        tree = ast.parse(source, filename=str(init_path))
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


def _is_not_implemented_error(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    if isinstance(func, ast.Name) and func.id == "NotImplementedError":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "NotImplementedError":
        return True
    return False


def _extract_message(expr: ast.Call) -> Optional[str]:
    if not expr.args:
        return None
    first = expr.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    try:
        value = ast.literal_eval(first)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _scan_not_implemented_sites() -> List[_NotImplementedSite]:
    pkg_root = _package_root()
    sites: List[_NotImplementedSite] = []

    for py_path in sorted(pkg_root.glob("*.py")):
        if py_path.name == "compat.py":
            continue

        try:
            source = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=str(py_path))
        except SyntaxError:
            continue

        module_name = f"numpy2.{py_path.stem}" if py_path.stem != "__init__" else "numpy2"
        scope: List[str] = []

        class _Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> Any:
                scope.append(node.name)
                self.generic_visit(node)
                scope.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
                scope.append(node.name)
                self.generic_visit(node)
                scope.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
                scope.append(node.name)
                self.generic_visit(node)
                scope.pop()

            def visit_Raise(self, node: ast.Raise) -> Any:
                if node.exc is not None and _is_not_implemented_error(node.exc):
                    exc = node.exc  # type: ignore[assignment]
                    message = _extract_message(exc)  # type: ignore[arg-type]
                    qualified = module_name + ("." + ".".join(scope) if scope else "")

                    kind = "stubbed"
                    msg_l = (message or "").lower()
                    if "axis not yet" in msg_l or "not yet fully supported" in msg_l:
                        kind = "partial"
                    elif "not yet supported" in msg_l or "not yet implemented" in msg_l:
                        kind = "high_risk"

                    sites.append(
                        _NotImplementedSite(
                            qualified_name=qualified,
                            message=message,
                            filepath=str(py_path),
                            line=getattr(node, "lineno", 1),
                            kind=kind,
                        )
                    )
                self.generic_visit(node)

        _Visitor().visit(tree)

    uniq: Dict[str, _NotImplementedSite] = {}
    for site in sites:
        uniq.setdefault(site.qualified_name, site)
    return list(uniq.values())


def report() -> Dict[str, Any]:
    """Return a structured compatibility report for numpy2."""

    version = _read_init_version()
    now = datetime.now(timezone.utc).isoformat()

    subset: Dict[str, Dict[str, Any]] = {
        "mgrid": {
            "status": "stubbed",
            "reason": "Prefer meshgrid/arange in numpy2 pure mode.",
        },
        "ogrid": {
            "status": "stubbed",
            "reason": "Prefer meshgrid/arange in numpy2 pure mode.",
        },
        "c_": {
            "status": "stubbed",
            "reason": "Not implemented in numpy2 yet.",
        },
        "r_": {
            "status": "stubbed",
            "reason": "Not implemented in numpy2 yet.",
        },
    }

    stubs = _scan_not_implemented_sites()
    counts = {"stubbed": 0, "partial": 0, "high_risk": 0}
    for site in stubs:
        counts[site.kind] = counts.get(site.kind, 0) + 1

    return {
        "package": "numpy2",
        "version": version,
        "python": sys.version.split()[0],
        "generated_at": now,
        "subset": subset,
        "not_implemented": [
            {
                "qualified_name": s.qualified_name,
                "kind": s.kind,
                "message": s.message,
                "file": s.filepath,
                "line": s.line,
            }
            for s in sorted(stubs, key=lambda x: (x.kind, x.qualified_name))
        ],
        "summary": {
            "not_implemented_count": len(stubs),
            "by_kind": counts,
        },
    }

