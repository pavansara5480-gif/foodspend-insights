"""Query-parameter parsing with clear 400 errors."""
from datetime import date

from rest_framework.exceptions import ValidationError


def get_date(request, name: str):
    v = request.query_params.get(name)
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise ValidationError({name: f"'{v}' is not a valid date (YYYY-MM-DD)"})


def get_float(request, name: str, default=None, minimum=None, maximum=None):
    v = request.query_params.get(name)
    if v in (None, ""):
        return default
    try:
        f = float(v)
    except ValueError:
        raise ValidationError({name: f"'{v}' is not a number"})
    if minimum is not None and f < minimum:
        raise ValidationError({name: f"must be >= {minimum}"})
    if maximum is not None and f > maximum:
        raise ValidationError({name: f"must be <= {maximum}"})
    return f


def get_int(request, name: str, default: int, minimum: int = 1, maximum: int = 1000) -> int:
    return int(get_float(request, name, default, minimum, maximum))


def get_choice(request, name: str, options, default=None):
    v = request.query_params.get(name, default)
    if v is not None and v not in options:
        raise ValidationError({name: f"must be one of {sorted(options)}"})
    return v


def period(request):
    start, end = get_date(request, "start"), get_date(request, "end")
    if start and end and start > end:
        raise ValidationError({"start": "start must be on or before end"})
    return start, end
