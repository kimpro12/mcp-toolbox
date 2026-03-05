from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def format_python_file(filepath: Path) -> bool:
    """Format a Python file with Ruff.

    Args:
        filepath: File path to format.

    Returns:
        True when Ruff exits successfully, otherwise False.
    """

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(filepath)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def format_project(directory: Path) -> None:
    """Run Ruff lint fixes and formatting for a project directory."""

    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix", "--exit-zero", str(directory)],
        capture_output=True,
        text=True,
        check=False,
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(directory)],
        capture_output=True,
        text=True,
        check=False,
    )


def validate_syntax(filepath: Path) -> tuple[bool, str]:
    """Compile a Python file and report syntax errors.

    Args:
        filepath: Python file to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """

    try:
        source = filepath.read_text(encoding="utf-8")
        compile(source, str(filepath), "exec")
        return True, ""
    except SyntaxError as exc:
        return False, f"Line {exc.lineno}: {exc.msg}"
