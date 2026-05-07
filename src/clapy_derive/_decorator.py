from __future__ import annotations

import argparse
import inspect
import os
from typing import Any

from ._field import MISSING, clapy_arg
from ._types import is_bool, unwrap_list, unwrap_optional


def _collect_fields(cls: type) -> dict[str, tuple[clapy_arg, Any]]:
    """Walk MRO to gather annotated fields, respecting class-level defaults."""
    annotations: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        if klass is object:
            continue
        # Skip Parser itself — it has no user fields
        if klass.__name__ == "Parser" and klass.__module__ == __name__:
            continue
        annotations.update(getattr(klass, "__annotations__", {}))

    fields: dict[str, tuple[clapy_arg, Any]] = {}
    for name, annotation in annotations.items():
        if name.startswith("_"):
            continue
        raw = cls.__dict__.get(name, MISSING)
        if isinstance(raw, clapy_arg):
            fields[name] = (raw, annotation)
        elif raw is MISSING:
            # No clapy_arg() → positional (mirrors clap: no #[arg(short, long)] = positional)
            fields[name] = (clapy_arg(short=False, long=False), annotation)
        else:
            # Plain Python default → optional positional
            fields[name] = (clapy_arg(short=False, long=False, default=raw), annotation)

    return fields


def _resolve_short(name: str, arg: clapy_arg, used: set[str]) -> str | None:
    if arg.short is False:
        return None
    char = arg.short if isinstance(arg.short, str) else name[0]
    if char in used:
        return None  # silently drop on collision (clap would panic)
    used.add(char)
    return char


def _resolve_long(name: str, arg: clapy_arg) -> str | None:
    if arg.long is False:
        return None
    return (arg.long if isinstance(arg.long, str) else name).replace("_", "-")


def _add_field(
    ap: argparse.ArgumentParser,
    name: str,
    arg: clapy_arg,
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

    # Resolve default: env var > clapy_arg.default > None (for Optional)
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


def _apply_parser(
    cls: type,
    builtins: tuple[str, ...],
    name: str | None,
    version: str | bool,
    about: str | None,
) -> type:
    """Core logic shared by @clapy_parser and ClapyParser inheritance."""
    fields = _collect_fields(cls)
    doc = about or inspect.cleandoc(cls.__doc__ or "")

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
        fields["verbose"] = (clapy_arg(short="v", long="verbose"), bool)

    for fname, (arg, annotation) in fields.items():
        if fname == "verbose" and "verbose" in builtins:
            continue
        _add_field(ap, fname, arg, annotation, used_shorts)

    for fname, (arg, _) in fields.items():
        if cls.__dict__.get(fname) is arg:
            try:
                delattr(cls, fname)
            except AttributeError:
                pass

    cls._clapy_argparser = ap
    cls._clapy_fields = fields

    # Inject parse() only for decorator usage; Parser subclasses inherit it.
    if not issubclass(cls, Parser):
        @classmethod  # type: ignore[misc]
        def parse(klass: type, args: list[str] | None = None) -> Any:
            namespace = ap.parse_args(args)
            instance = object.__new__(klass)
            for fname in fields:
                setattr(instance, fname, getattr(namespace, fname))
            return instance

        cls.parse = parse

    return cls


class Parser:
    """Base class alternative to ``@clapy_parser``.

    Inherit from this class to turn a class into a CLI parser without a decorator.
    Parser options can be passed as class keyword arguments.

    Example::

        class Cli(Parser, builtins=("version", "verbose")):
            input: str = clapy_arg(short=True, long=True)

        cli = Cli.parse()
    """

    _clapy_argparser: argparse.ArgumentParser
    _clapy_fields: dict[str, tuple[clapy_arg, Any]]

    @classmethod
    def parse(cls, args: list[str] | None = None) -> "Parser":
        """Parse ``args`` (defaults to ``sys.argv[1:]``) and return a populated instance."""
        namespace = cls._clapy_argparser.parse_args(args)
        instance = object.__new__(cls)
        for fname in cls._clapy_fields:
            setattr(instance, fname, getattr(namespace, fname))
        return instance

    def __init_subclass__(
        cls,
        *,
        builtins: tuple[str, ...] | list[str] = (),
        name: str | None = None,
        version: str | bool = False,
        about: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        _apply_parser(cls, tuple(builtins), name, version, about)


def clapy_parser(
    _first: type | str | None = None,
    /,
    *rest_builtins: str,
    name: str | None = None,
    version: str | bool = False,
    about: str | None = None,
):
    """Decorate a class to turn it into a CLI parser.

    Supports both ``@clapy_parser`` and ``@clapy_parser()`` forms.
    Built-in flags (passed as positional strings): ``'version'``, ``'verbose'``.

    Args:
        *builtins: Built-in flags to add (``'version'``, ``'verbose'``).
        name: Override the program name (defaults to class name lowercased).
        version: Version string, or ``True`` to read from package metadata.
        about: Description shown in ``--help`` (defaults to class docstring).
    """
    if isinstance(_first, type):
        _cls: type | None = _first
        builtins: tuple[str, ...] = rest_builtins
    elif isinstance(_first, str):
        _cls = None
        builtins = (_first, *rest_builtins)
    else:
        _cls = None
        builtins = rest_builtins

    def decorator(cls: type) -> type:
        return _apply_parser(cls, builtins, name, version, about)

    if _cls is not None:
        return decorator(_cls)
    return decorator
