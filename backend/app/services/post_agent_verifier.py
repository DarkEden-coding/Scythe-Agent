"""Post-agent verification: run ruff, ty, py_compile, tsc on edited files."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_VERIFICATION_PREFIX = "The following lint/type issues were found"
_TIMEOUT = 60


@dataclass
class VerificationIssue:
    """A single issue from a checker."""

    file: str
    line: int
    column: int | None
    code: str | None
    message: str
    tool: str


def _format_summary(
    issues: list[VerificationIssue],
) -> tuple[str, dict[str, int]]:
    """Build human-readable summary and by-tool counts."""
    by_tool: dict[str, int] = {}
    for iss in issues:
        by_tool[iss.tool] = by_tool.get(iss.tool, 0) + 1
    unique_files = len({iss.file for iss in issues})
    parts = [f"{len(issues)} issue" + ("s" if len(issues) != 1 else "")]
    parts.append(f"in {unique_files} file" + ("s" if unique_files != 1 else ""))
    if by_tool:
        tool_parts = [f"{c} {t}" for t, c in sorted(by_tool.items())]
        parts.append(f"({', '.join(tool_parts)})")
    return (" ".join(parts), by_tool)


def _format_for_agent(issues: list[VerificationIssue]) -> str:
    """Format issues for the agent message content."""
    lines = [
        f"{_VERIFICATION_PREFIX} in files you edited. Please verify they are real problems and fix them:",
        "",
    ]
    for iss in issues:
        loc = f"{iss.file}:{iss.line}"
        if iss.column is not None:
            loc += f":{iss.column}"
        line = f"[{iss.tool}] {loc}: {iss.message}"
        if iss.code:
            line = f"[{iss.tool}] {loc}: {iss.code} {iss.message}"
        lines.append(line)
    return "\n".join(lines)


def _is_python(path: str) -> bool:
    return Path(path).suffix == ".py"


def _is_ts_or_js(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in (".ts", ".tsx", ".js", ".jsx")


async def _run_cmd(
    cmd: list[str],
    cwd: str | Path,
    timeout: int = _TIMEOUT,
) -> tuple[str, str, int]:
    """Run command; return (stdout, stderr, returncode)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        logger.warning("Verification subprocess timed out: %s", cmd[:2])
        return ("", f"Timed out after {timeout}s", 1)
    except Exception as e:
        logger.warning("Verification subprocess failed: %s", e)
        return ("", str(e), 1)


async def _run_ruff(paths: list[str], project_root: Path) -> list[VerificationIssue]:
    """Run ruff check on Python paths."""
    if not paths:
        return []
    issues: list[VerificationIssue] = []
    for p in paths:
        if not Path(p).exists():
            continue
        out, err, code = await _run_cmd(
            ["ruff", "check", p, "--output-format=json"],
            cwd=project_root,
        )
        if out:
            try:
                data = json.loads(out)
                for d in data:
                    loc = d.get("location", {})
                    issues.append(
                        VerificationIssue(
                            file=d.get("filename", p),
                            line=loc.get("row", 0),
                            column=loc.get("column"),
                            code=d.get("code"),
                            message=d.get("message", ""),
                            tool="ruff",
                        )
                    )
            except json.JSONDecodeError:
                if err:
                    issues.append(
                        VerificationIssue(
                            file=p,
                            line=0,
                            column=None,
                            code=None,
                            message=err.strip() or out.strip(),
                            tool="ruff",
                        )
                    )
    return issues


def _parse_ty_line(line: str, base_path: str) -> VerificationIssue | None:
    """Parse a single ty error line. Format: path:line:col: message or error[...]: message."""
    m = re.match(r"^(.+?):(\d+):(\d+):\s*(.+)", line)
    if m:
        path, row, col, rest = m.groups()
        return VerificationIssue(
            file=path,
            line=int(row),
            column=int(col),
            code=None,
            message=rest.strip(),
            tool="ty",
        )
    m = re.match(r"^error\[([^\]]+)\]:\s*(.+)$", line.strip())
    if m:
        return VerificationIssue(
            file=base_path,
            line=0,
            column=None,
            code=m.group(1),
            message=m.group(2).strip(),
            tool="ty",
        )
    return None


async def _run_ty(paths: list[str], project_root: Path) -> list[VerificationIssue]:
    """Run ty check on Python paths."""
    if not paths:
        return []
    issues: list[VerificationIssue] = []
    for p in paths:
        if not Path(p).exists():
            continue
        out, err, code = await _run_cmd(
            ["ty", "check", p],
            cwd=project_root,
        )
        text = (out + "\n" + err).strip()
        if code != 0 and text:
            for raw in text.split("\n"):
                iss = _parse_ty_line(raw, p)
                if iss:
                    issues.append(iss)
            if not issues and text:
                issues.append(
                    VerificationIssue(
                        file=p,
                        line=0,
                        column=None,
                        code=None,
                        message=text[:500],
                        tool="ty",
                    )
                )
    return issues


async def _run_py_compile(paths: list[str], project_root: Path) -> list[VerificationIssue]:
    """Run py_compile on Python paths."""
    if not paths:
        return []
    issues: list[VerificationIssue] = []
    for p in paths:
        if not Path(p).exists():
            continue
        _, err, code = await _run_cmd(
            ["python", "-m", "py_compile", p],
            cwd=project_root,
        )
        if code != 0 and err:
            m = re.search(r"line\s+(\d+)", err, re.I)
            line_num = int(m.group(1)) if m else 0
            issues.append(
                VerificationIssue(
                    file=p,
                    line=line_num,
                    column=None,
                    code=None,
                    message=err.strip(),
                    tool="py_compile",
                )
            )
    return issues


def _tsc_line_matches_edited(line: str, edited_paths: set[str]) -> bool:
    """Check if tsc error line references one of our edited paths."""
    m = re.match(r"^([^(]+)\(\d+,\d+\):", line)
    if m:
        path = m.group(1).strip()
        for ep in edited_paths:
            if path.endswith(ep) or ep.endswith(path):
                return True
        if any(Path(ep).name == Path(path).name for ep in edited_paths):
            return True
    return False


async def _run_tsc(
    paths: list[str], project_root: Path
) -> list[VerificationIssue]:
    """Run tsc --noEmit and filter output to edited paths."""
    if not paths:
        return []
    edited_set = {str(Path(p).resolve()) for p in paths}
    out, err, code = await _run_cmd(
        ["npx", "tsc", "--noEmit"],
        cwd=project_root,
    )
    text = (out + "\n" + err).strip()
    if code != 0 and text:
        issues: list[VerificationIssue] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or "error TS" not in line:
                continue
            m = re.match(r"^([^(]+)\((\d+),(\d+)\):\s*error\s+(TS\d+):?\s*(.*)$", line)
            if m:
                path, row, col, ts_code, msg = m.groups()
                path = path.strip()
                if not _tsc_line_matches_edited(line, edited_set):
                    continue
                abs_path = str((project_root / path).resolve()) if not Path(path).is_absolute() else path
                issues.append(
                    VerificationIssue(
                        file=abs_path,
                        line=int(row),
                        column=int(col),
                        code=ts_code,
                        message=msg.strip(),
                        tool="tsc",
                    )
                )
        if not issues:
            for line in text.split("\n"):
                if _tsc_line_matches_edited(line, edited_set):
                    issues.append(
                        VerificationIssue(
                            file=paths[0] if paths else ".",
                            line=0,
                            column=None,
                            code=None,
                            message=line[:300],
                            tool="tsc",
                        )
                    )
                    break
        return issues
    return []


async def run_verification(
    edited_file_paths: list[str],
    project_root: str,
) -> tuple[list[VerificationIssue], str, dict[str, int]]:
    """Run all checkers on edited files. Returns (issues, summary, by_tool)."""
    root = Path(project_root)
    py_paths = [p for p in edited_file_paths if _is_python(p)]
    ts_paths = [p for p in edited_file_paths if _is_ts_or_js(p)]

    all_issues: list[VerificationIssue] = []

    if py_paths:
        r, t, c = await asyncio.gather(
            _run_ruff(py_paths, root),
            _run_ty(py_paths, root),
            _run_py_compile(py_paths, root),
        )
        all_issues.extend(r)
        all_issues.extend(t)
        all_issues.extend(c)

    if ts_paths:
        tsc_issues = await _run_tsc(ts_paths, root)
        all_issues.extend(tsc_issues)

    summary, by_tool = _format_summary(all_issues)
    return (all_issues, summary, by_tool)


def format_message_for_agent(issues: list[VerificationIssue]) -> str:
    """Format full issue list for the agent message content."""
    return _format_for_agent(issues)


def is_verification_message(content: str) -> bool:
    """Check if user message is the verification prompt (to avoid re-verifying)."""
    return content.strip().startswith(_VERIFICATION_PREFIX)
