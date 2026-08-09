#!/usr/bin/env python3
"""MCP facade for the JellySSH independent-review boundary."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_boundary import ReviewRepository  # noqa: E402


ROOT = os.environ.get("JELLYSSH_REVIEW_ROOT", "").strip()
EXPECTED = os.environ.get("JELLYSSH_EXPECTED_COMMIT", "").strip()
BASE = os.environ.get("JELLYSSH_REVIEW_BASE_COMMIT", EXPECTED).strip()
SSH_TARGET = os.environ.get("JELLYSSH_REVIEW_SSH_TARGET", "").strip()
if not ROOT:
    raise RuntimeError("JELLYSSH_REVIEW_ROOT is required")

repo = ReviewRepository(
    ROOT,
    EXPECTED or None,
    SSH_TARGET or None,
    allowed_refs={value for value in (EXPECTED, BASE) if value},
    base_commit=BASE or None,
)
mcp = FastMCP("jellyssh-review-readonly")
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


@mcp.tool(annotations=READ_ONLY)
def repository_metadata() -> dict[str, object]:
    """Return exact review-root, commit, branch, origin, and cleanliness metadata."""
    return repo.metadata()


@mcp.tool(annotations=READ_ONLY)
def list_repository_files(pattern: str = "*", limit: int = 200) -> list[str]:
    """List contained non-.git files matching a glob; no filesystem writes."""
    return repo.list_files(pattern, limit)


@mcp.tool(annotations=READ_ONLY)
def read_repository_text(relative_path: str, start_line: int = 1, max_lines: int = 400) -> str:
    """Read bounded UTF-8 text contained in the review root; credentials are denied."""
    return repo.read_text(relative_path, start_line, max_lines)


@mcp.tool(annotations=READ_ONLY)
def review_git_diff(base: str, target: str = "HEAD", paths: list[str] | None = None) -> str:
    """Read an exact Git diff using fixed no-external-diff arguments."""
    return repo.git_diff(base, target, paths)


@mcp.tool(annotations=READ_ONLY)
def review_git_show(ref: str, relative_path: str) -> str:
    """Read one tracked file at an exact Git ref with external helpers disabled."""
    return repo.git_show(ref, relative_path)


@mcp.tool(annotations=READ_ONLY)
def run_readonly_check(name: str) -> str:
    """Run one fixed Git check or sandboxed Flutter/analyze/test/format check."""
    return repo.run_check(name)


if __name__ == "__main__":
    mcp.run()
