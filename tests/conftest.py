"""Shared test helpers and fixtures."""

from __future__ import annotations


class DummyCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess used across test modules."""

    def __init__(
        self,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
