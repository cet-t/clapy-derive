from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin


def unwrap_optional(annotation: Any) -> tuple[bool, Any]:
    """Return (is_optional, inner_type).

    Handles both `X | None` (3.10+) and `Optional[X]`.
    """
    origin = get_origin(annotation)
    if origin is Union or (
        hasattr(types, "UnionType") and isinstance(annotation, types.UnionType)
    ):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) < len(args):  # at least one None in the union
            inner = non_none[0] if len(non_none) == 1 else Union[tuple(non_none)]
            return True, inner
    return False, annotation


def unwrap_list(annotation: Any) -> tuple[bool, Any]:
    """Return (is_list, element_type).

    Handles `list[T]`.
    """
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        return True, args[0] if args else str
    return False, annotation


def is_bool(annotation: Any) -> bool:
    return annotation is bool
