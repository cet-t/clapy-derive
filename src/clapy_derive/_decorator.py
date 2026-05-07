from __future__ import annotations

import argparse
import inspect
import os
from typing import Any

from ._field import Arg, MISSING
from ._types import is_bool, unwrap_list, unwrap_optional


def _collect_fields(cls: type) -> dict[str, tuple[Arg, Any]]:
    """Walk MRO to gather annotated fields, respecting class-level defaults."""
    annotations: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        if klass is object:
            continue
        annotations.update(getattr(klass, "__annotations__", {}))

    fields: dict[str, tuple[Arg, Any]] = {}
    for name, annotation in annotations.items():
        if name.startswith("_"):
            continue
        raw = cls.__dict__.get(name, MISSING)
        if isinstance(raw, Arg):
            fields[name] = (raw, annotation)
        elif raw is MISSING:
            # No Arg() → positional (mirrors clap: no #[arg(short, long)] = positional)
            fields[name] = (Arg(short=False, long=False), annotation)
        else:
            # Plain Python default → optional positional
            fields[name] = (Arg(short=False, long=False, default=raw), annotation)

    return fields


def _resolve_short(name: str, arg: Arg, used: set[str]) -> str | None:
    if arg.short is False:
        return None
    char = arg.short if isinstance(arg.short, str) else name[0]
    if char in used:
        return None  # silently drop on collision (clap would panic)
    used.add(char)
    return char


def _resolve_long(name: str, arg: Arg) -> str | None:
    if arg.long is False:
        return None
    return (arg.long if isinstance(arg.long, str) else name).replace("_", "-")


def _add_field(
    ap: argparse.ArgumentParser,
    name: str,
    arg: Arg,
    annotation: Any,
    used_shorts: set[str],
) -> None:
    is_opt, inner = unwrap_optional(annotation)
    is_lst, elem_type = unwrap_list(inner)
    as_bool = is_bool(inner)

    short_char = _resolve_short(name, arg, used_shorts)
    long_name = _resolve_long(name, arg)

    flags: list[str] = []
    if short_char:
        flags.append(f"-{short_char}")
    if long_name:
        flags.append(f"--{long_name}")

    # Resolve default: env var > Arg.default > None (for Optional)
    env_default = MISSING
    if arg.env:
        env_val = os.environ.get(arg.env)
        if env_val is not None:
            env_default = env_val

    effective_default = env_default if env_default is not MISSING else arg.default
    has_default = effective_default is not MISSING
    if not has_default and is_opt:
        effective_default = None
        has_default = True

    kw: dict[str, Any] = {}
    if arg.help:
        kw["help"] = arg.help
    if arg.choices:
        kw["choices"] = arg.choices
    if arg.metavar:
        kw["metavar"] = arg.metavar

    if flags:
        # Named (optional-style) argument
        kw["dest"] = name

        if as_bool:
            kw["action"] = "store_true"
            kw["default"] = effective_default if has_default else False
        elif is_lst:
            kw["type"] = elem_type if elem_type is not str else None
            kw["nargs"] = "+"
            if has_default:
                kw["default"] = effective_default
            else:
                kw["required"] = True
        else:
            if inner is not str:
                kw["type"] = inner
            if has_default:
                kw["default"] = effective_default
            else:
                kw["required"] = True

        ap.add_argument(*flags, **kw)

    else:
        # Positional argument
        if is_lst:
            kw["nargs"] = "*" if has_default else "+"
            kw["type"] = elem_type if elem_type is not str else None
        elif is_opt or has_default:
            kw["nargs"] = "?"
        elif not as_bool and inner is not str:
            kw["type"] = inner

        if has_default:
            kw["default"] = effective_default

        ap.add_argument(name, **kw)


def clapy_parser(
    *builtins: str,
    name: str | None = None,
    version: str | bool = False,
    about: str | None = None,
):
    """Decorate a class to turn it into a CLI parser.

    Built-in flags (passed as positional strings): ``'version'``, ``'verbose'``.

    Args:
        *builtins: Built-in flags to add (``'version'``, ``'verbose'``).
        name: Override the program name (defaults to class name lowercased).
        version: Version string, or ``True`` to read from package metadata.
        about: Description shown in ``--help`` (defaults to class docstring).
    """

    def decorator(cls: type) -> type:
        fields = _collect_fields(cls)
        doc = about or inspect.cleandoc(cls.__doc__ or "")

        # Resolve version string
        ver_str: str | None = None
        if "version" in builtins or version:
            if isinstance(version, str):
                ver_str = version
            else:
                try:
                    from importlib.metadata import version as _pkg_version

                    ver_str = _pkg_version(cls.__module__.split(".")[0])
                except Exception:
                    ver_str = "0.0.0"

        prog = name or cls.__name__.lower()
        ap = argparse.ArgumentParser(prog=prog, description=doc or None)

        # Track used short chars; reserve built-in chars up front
        used_shorts: set[str] = set()
        if ver_str:
            used_shorts.add("V")
        if "verbose" in builtins:
            used_shorts.add("v")

        if ver_str:
            ap.add_argument(
                "-V", "--version", action="version", version=f"%(prog)s {ver_str}"
            )

        if "verbose" in builtins and "verbose" not in fields:
            ap.add_argument(
                "-v", "--verbose", action="store_true", help="Enable verbose output"
            )
            fields["verbose"] = (Arg(short="v", long="verbose"), bool)

        for fname, (arg, annotation) in fields.items():
            if fname == "verbose" and "verbose" in builtins:
                continue  # already added above
            _add_field(ap, fname, arg, annotation, used_shorts)

        # Remove Arg sentinels from the class so instances can hold real values
        for fname, (arg, _) in fields.items():
            if cls.__dict__.get(fname) is arg:
                try:
                    delattr(cls, fname)
                except AttributeError:
                    pass

        cls._clapy_argparser = ap
        cls._clapy_fields = fields

        @classmethod  # type: ignore[misc]
        def parse(klass: type, args: list[str] | None = None) -> Any:
            namespace = ap.parse_args(args)
            instance = object.__new__(klass)
            for fname in fields:
                setattr(instance, fname, getattr(namespace, fname))
            return instance

        cls.parse = parse
        return cls

    return decorator
