from __future__ import annotations

from typing import Any

MISSING: Any = object()


class Arg:
    """Metadata for a CLI argument field — mirrors clap's #[arg(...)] attribute."""

    def __init__(
        self,
        *,
        short: bool | str = False,
        long: bool | str = True,
        help: str = "",
        default: Any = MISSING,
        choices: list | None = None,
        metavar: str | None = None,
        env: str | None = None,
    ) -> None:
        self.short = short      # True=auto (first char), str=explicit char, False=off
        self.long = long        # True=auto (field name), str=explicit name, False=off
        self.help = help
        self.default = default  # MISSING = required
        self.choices = choices
        self.metavar = metavar
        self.env = env

    @property
    def required(self) -> bool:
        return self.default is MISSING

    def __repr__(self) -> str:
        return (
            f"Arg(short={self.short!r}, long={self.long!r}, "
            f"help={self.help!r}, default={self.default!r})"
        )
