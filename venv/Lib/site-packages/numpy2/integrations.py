"""
numpy2.integrations - Web framework helpers

Zero-configuration integrations for FastAPI, Flask, Django.
No NumPy import required.
"""

import json
from typing import Any, Optional, Callable

from .core import serialize, JSONEncoder


def FastAPIResponse(
    content: Any,
    status_code: int = 200,
    headers: Optional[dict] = None,
    media_type: str = "application/json",
) -> dict:
    """
    Create a FastAPI-compatible JSON response from numpy2 / pandas data.

    Example:
        >>> from fastapi.responses import JSONResponse
        >>> import numpy2 as np2
        >>> @app.get("/data")
        ... def get_data():
        ...     arr = np2.array([1, 2, 3])
        ...     return JSONResponse(np2.FastAPIResponse(arr))
    """
    serialized = serialize(content, include_metadata=False)
    return {
        "body": json.dumps(serialized, cls=JSONEncoder).encode("utf-8"),
        "status_code": status_code,
        "headers": headers or {},
        "media_type": media_type,
    }


def FlaskResponse(
    content: Any,
    status: int = 200,
    headers: Optional[dict] = None,
    mimetype: str = "application/json",
) -> str:
    """
    Create a Flask-compatible JSON string from numpy2 / pandas data.

    Example:
        >>> import numpy2 as np2
        >>> @app.route("/data")
        ... def get_data():
        ...     arr = np2.array([1, 2, 3])
        ...     return np2.FlaskResponse(arr)
    """
    serialized = serialize(content, include_metadata=False)
    return json.dumps(serialized, cls=JSONEncoder)


def DjangoResponse(
    content: Any,
    safe: bool = True,
    status: int = 200,
) -> str:
    """
    Create a Django-compatible JSON string from numpy2 / pandas data.

    Example:
        >>> from django.http import JsonResponse
        >>> import numpy2 as np2
        >>> def get_data(request):
        ...     arr = np2.array([1, 2, 3])
        ...     return JsonResponse(json.loads(np2.DjangoResponse(arr)), safe=True)
    """
    serialized = serialize(content, include_metadata=False)
    return json.dumps(serialized, cls=JSONEncoder)


def setup_json_encoder(framework: str = "fastapi") -> None:
    """
    Patch a web framework's JSON encoder to handle numpy2 / NumPy / pandas types.

    Args:
        framework: 'fastapi', 'flask', or 'django'

    Example:
        >>> import numpy2 as np2
        >>> np2.setup_json_encoder("flask")
    """
    fw = framework.lower()

    if fw == "fastapi":
        try:
            import fastapi
            _patch_fastapi_encoder()
        except ImportError:
            raise ImportError("FastAPI not installed. Run: pip install fastapi")

    elif fw == "flask":
        try:
            import flask
            _patch_flask_encoder()
        except ImportError:
            raise ImportError("Flask not installed. Run: pip install flask")

    elif fw == "django":
        try:
            import django
            _patch_django_encoder()
        except ImportError:
            raise ImportError("Django not installed. Run: pip install django")

    else:
        raise ValueError(f"Unknown framework: {framework!r}. Use 'fastapi', 'flask', or 'django'.")


def _patch_fastapi_encoder() -> None:
    try:
        from numpy2.array import ndarray as _ndarray
        import fastapi.encoders as _enc
        _orig = _enc.jsonable_encoder

        def _patched(obj, *args, **kwargs):
            if isinstance(obj, _ndarray):
                return obj.tolist()
            return _orig(obj, *args, **kwargs)

        _enc.jsonable_encoder = _patched
    except Exception:
        pass


def _patch_flask_encoder() -> None:
    try:
        from flask.json.provider import DefaultJSONProvider
        from numpy2.array import ndarray as _ndarray

        _orig_default = DefaultJSONProvider.default

        def _new_default(self, o):
            if isinstance(o, _ndarray):
                return o.tolist()
            try:
                import pandas as _pd
                if isinstance(o, _pd.DataFrame):
                    return o.to_dict(orient='records')
                if isinstance(o, _pd.Series):
                    return o.to_dict()
            except ImportError:
                pass
            return _orig_default(self, o)

        DefaultJSONProvider.default = _new_default
    except Exception:
        pass


def _patch_django_encoder() -> None:
    try:
        from django.core.serializers.json import DjangoJSONEncoder
        from numpy2.array import ndarray as _ndarray

        _orig_default = DjangoJSONEncoder.default

        def _new_default(self, o):
            if isinstance(o, _ndarray):
                return o.tolist()
            try:
                import pandas as _pd
                if isinstance(o, _pd.DataFrame):
                    return o.to_dict(orient='records')
                if isinstance(o, _pd.Series):
                    return o.to_dict()
            except ImportError:
                pass
            return _orig_default(self, o)

        DjangoJSONEncoder.default = _new_default
    except Exception:
        pass


def create_response_handler(
    framework: str,
    include_metadata: bool = False,
) -> Callable:
    """
    Create a framework-specific handler that serializes numpy2 data.

    Example:
        >>> import numpy2 as np2
        >>> handler = np2.create_response_handler("fastapi", include_metadata=True)
        >>> response = handler(np2.array([1, 2, 3]))
    """
    def handler(content: Any) -> Any:
        serialized = serialize(content, include_metadata=include_metadata)
        fw = framework.lower()
        if fw == "fastapi":
            return serialized
        if fw in ("flask", "django"):
            return json.dumps(serialized, cls=JSONEncoder)
        return serialized

    return handler
