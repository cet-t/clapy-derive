"""clapy-derive — a clap-inspired declarative CLI argument parser for Python."""

from ._decorator import clapy_parser
from ._field import Arg, MISSING

clapy_arg = Arg  # primary public alias

__all__ = ["Arg", "clapy_arg", "clapy_parser", "MISSING"]
