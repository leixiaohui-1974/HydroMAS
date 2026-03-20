"""Pytest-wide compatibility hooks for HydroMAS."""

from __future__ import annotations

import builtins
import io
from typing import Any


_builtin_open = builtins.open
_io_open = io.open


def _inject_utf8(mode: str, encoding: str | None) -> str | None:
    if "b" in mode or encoding is not None:
        return encoding
    return "utf-8"


def _patched_open(
    file: Any,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    closefd: bool = True,
    opener: Any = None,
):
    return _builtin_open(
        file,
        mode,
        buffering=buffering,
        encoding=_inject_utf8(mode, encoding),
        errors=errors,
        newline=newline,
        closefd=closefd,
        opener=opener,
    )


def _patched_io_open(
    file: Any,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    closefd: bool = True,
    opener: Any = None,
):
    return _io_open(
        file,
        mode,
        buffering=buffering,
        encoding=_inject_utf8(mode, encoding),
        errors=errors,
        newline=newline,
        closefd=closefd,
        opener=opener,
    )


builtins.open = _patched_open
io.open = _patched_io_open
