"""HydroMAS interpreter defaults.

Force UTF-8 for implicit text-mode file operations on Windows so the test
suite behaves consistently with the repository's UTF-8 source and data files.
"""

from __future__ import annotations

import builtins
import io
from typing import Any


_builtin_open = builtins.open
_io_open = io.open


def _should_inject_utf8(mode: str, encoding: str | None) -> bool:
    return "b" not in mode and encoding is None


def _open_with_utf8_default(
    file: Any,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    closefd: bool = True,
    opener: Any = None,
):
    if _should_inject_utf8(mode, encoding):
        encoding = "utf-8"
    return _builtin_open(
        file,
        mode,
        buffering=buffering,
        encoding=encoding,
        errors=errors,
        newline=newline,
        closefd=closefd,
        opener=opener,
    )


def _io_open_with_utf8_default(
    file: Any,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    closefd: bool = True,
    opener: Any = None,
):
    if _should_inject_utf8(mode, encoding):
        encoding = "utf-8"
    return _io_open(
        file,
        mode,
        buffering=buffering,
        encoding=encoding,
        errors=errors,
        newline=newline,
        closefd=closefd,
        opener=opener,
    )


builtins.open = _open_with_utf8_default
io.open = _io_open_with_utf8_default
