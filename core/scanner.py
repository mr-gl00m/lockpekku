from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import psutil  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

MOVE_PROBE_ENTRY_LIMIT = 25_000

SECRET_OPTION_NAMES = frozenset(
    {
        "access-token",
        "api-key",
        "apikey",
        "auth-token",
        "authorization",
        "client-secret",
        "password",
        "passwd",
        "private-key",
        "pwd",
        "refresh-token",
        "secret",
        "token",
    }
)


@dataclass(frozen=True)
class LockReason:
    kind: str  # "exe", "cwd", or "cmdline"
    path: str


@dataclass(frozen=True)
class LockHolder:
    pid: int
    name: str
    started: datetime | None
    cmdline: str
    reasons: tuple[LockReason, ...]

    @property
    def reason_summary(self) -> str:
        return ", ".join(r.kind for r in self.reasons)

    @property
    def locked_paths(self) -> str:
        return " | ".join(r.path for r in self.reasons)


@dataclass(frozen=True)
class KillResult:
    pid: int
    name: str
    outcome: str


def _norm(path_str: str) -> str:
    return os.path.normpath(path_str).casefold()


def _under(candidate: str, root_norm: str) -> bool:
    cand = _norm(candidate)
    return cand == root_norm or cand.startswith(root_norm.rstrip(os.sep) + os.sep)


def _strictly_under(candidate: str, root_norm: str) -> bool:
    cand = _norm(candidate)
    base = root_norm.rstrip(os.sep)
    # drive roots normalize with a trailing separator, so the prefix check
    # alone would treat "N:\" as strictly under "N:\"; equality is never under
    if cand == base or cand == base + os.sep:
        return False
    return cand.startswith(base + os.sep)


def _secret_option_name(value: str) -> str:
    return value.lstrip("-/").replace("_", "-").casefold()


def _redact_command_line(tokens: Iterable[str]) -> str:
    redacted: list[str] = []
    redact_next = False
    for token in tokens:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue

        assignment_redacted = False
        for separator in ("=", ":"):
            option, found, _value = token.partition(separator)
            if found and _secret_option_name(option) in SECRET_OPTION_NAMES:
                redacted.append(f"{option}{separator}<redacted>")
                assignment_redacted = True
                break
        if assignment_redacted:
            continue

        redacted.append(token)
        if _secret_option_name(token) in SECRET_OPTION_NAMES:
            redact_next = True

    return " ".join(redacted)


def _escape_report_text(value: object) -> str:
    return (
        str(value)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .replace("`", "'")
        .replace("|", "&#124;")
        .replace("@", "@\u200b")
    )


def scan(root: Path) -> list[LockHolder]:
    """Find processes that can block moves and renames under ``root``.

    Three lock vectors, matching the failures actually seen on this machine:
    an executable running from inside the tree, a working directory inside the
    tree, or a command-line argument naming a path inside the tree.
    """
    root = Path(root).resolve()
    root_norm = _norm(str(root))
    own_pid = os.getpid()
    holders: list[LockHolder] = []

    attrs = ["pid", "name", "exe", "cmdline", "create_time", "cwd"]
    for proc in psutil.process_iter(attrs=attrs, ad_value=None):
        info = proc.info
        pid: int = info["pid"]
        if pid == own_pid:
            continue

        reasons: list[LockReason] = []

        exe = info.get("exe")
        if exe and _under(exe, root_norm):
            reasons.append(LockReason("exe", exe))

        cwd = info.get("cwd")
        cwd_at_movable_root = (
            bool(cwd) and root.parent != root and _norm(cwd) == root_norm
        )
        if cwd and (cwd_at_movable_root or _strictly_under(cwd, root_norm)):
            reasons.append(LockReason("cwd", cwd))

        cmdline_tokens = info.get("cmdline") or []
        for token in cmdline_tokens:
            cleaned = token.strip('"').replace("/", os.sep)
            if cleaned and _strictly_under(cleaned, root_norm):
                reasons.append(LockReason("cmdline", cleaned))
                break

        if not reasons:
            continue

        started: datetime | None = None
        create_time = info.get("create_time")
        if create_time is not None:
            started = datetime.fromtimestamp(create_time)

        holders.append(
            LockHolder(
                pid=pid,
                name=info.get("name") or "?",
                started=started,
                cmdline=_redact_command_line(cmdline_tokens),
                reasons=tuple(reasons),
            )
        )

    holders.sort(key=lambda h: (h.name.casefold(), h.pid))
    return holders


def kill_processes(
    targets: Iterable[LockHolder | int], grace_seconds: float = 3.0
) -> list[KillResult]:
    """Terminate, wait, then hard-kill survivors. One result per target."""
    results: list[KillResult] = []
    waiting: list[psutil.Process] = []

    for target in targets:
        if isinstance(target, LockHolder):
            pid = target.pid
            expected_started = target.started
            if expected_started is None:
                results.append(KillResult(pid, target.name, "identity unavailable"))
                continue
        else:
            pid = target
            expected_started = None

        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if (
                expected_started is not None
                and datetime.fromtimestamp(proc.create_time()) != expected_started
            ):
                results.append(KillResult(pid, name, "changed"))
                logger.warning("Refused kill of reused pid %d (%s)", pid, name)
                continue
            proc.terminate()
            waiting.append(proc)
            logger.info("Sent terminate to pid %d (%s)", pid, name)
        except psutil.NoSuchProcess:
            results.append(KillResult(pid, "?", "gone"))
        except psutil.AccessDenied:
            results.append(KillResult(pid, "?", "denied"))
        except psutil.Error as exc:
            results.append(KillResult(pid, "?", f"error: {exc}"))

    gone, alive = psutil.wait_procs(waiting, timeout=grace_seconds)
    for proc in gone:
        results.append(KillResult(proc.pid, _safe_name(proc), "terminated"))

    for proc in alive:
        try:
            proc.kill()
            proc.wait(timeout=grace_seconds)
            results.append(KillResult(proc.pid, _safe_name(proc), "killed"))
            logger.info("Hard-killed pid %d", proc.pid)
        except psutil.NoSuchProcess:
            results.append(KillResult(proc.pid, "?", "gone"))
        except psutil.AccessDenied:
            results.append(KillResult(proc.pid, _safe_name(proc), "denied"))
        except psutil.Error as exc:
            results.append(KillResult(proc.pid, _safe_name(proc), f"error: {exc}"))

    return results


def _safe_name(proc: psutil.Process) -> str:
    try:
        return proc.name()
    except psutil.Error:
        return "?"


def probe_move(root: Path) -> tuple[bool, str]:
    """Check delete sharing across ``root`` without renaming the tree.

    Windows requires compatible delete sharing for rename operations. Opening
    each current entry with DELETE access, one at a time, identifies
    incompatible raw handles while leaving the directory namespace unchanged.
    """
    root = Path(root).absolute()
    if root.parent == root:
        return False, "refusing to probe a drive root"
    if sys.platform != "win32":
        return False, "move probe is available on Windows only"
    if not root.is_dir():
        return False, f"probe target is not a directory: {root}"

    entries: list[tuple[Path, bool]] = [(root, True)]

    def raise_walk_error(error: OSError) -> None:
        raise error

    try:
        for current, directory_names, file_names in os.walk(
            root, onerror=raise_walk_error
        ):
            current_path = Path(current)
            entries.extend((current_path / name, True) for name in directory_names)
            entries.extend((current_path / name, False) for name in file_names)
            # shortcut: this ceiling bounds probe time on huge trees; move the
            # probe to a worker and stream batches if larger trees become a target
            if len(entries) > MOVE_PROBE_ENTRY_LIMIT:
                return (
                    False,
                    f"probe incomplete: tree exceeds {MOVE_PROBE_ENTRY_LIMIT} entries",
                )
    except OSError as exc:
        return False, f"probe incomplete: could not enumerate tree: {exc}"

    delete_access = 0x00010000
    share_read = 0x00000001
    share_write = 0x00000002
    share_delete = 0x00000004
    open_existing = 3
    flag_backup_semantics = 0x02000000
    flag_open_reparse_point = 0x00200000
    invalid_handle = ctypes.c_void_p(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    error_file_not_found = 2
    error_path_not_found = 3
    error_sharing_violation = 32

    # open, check, close per entry: detecting an existing incompatible handle
    # does not require holding the probes simultaneously, and this keeps the
    # probe at one outstanding native handle instead of one per entry
    for path, is_directory in entries:
        flags = flag_open_reparse_point
        if is_directory:
            flags |= flag_backup_semantics
        handle = create_file(
            str(path),
            delete_access,
            share_read | share_write | share_delete,
            None,
            open_existing,
            flags,
            None,
        )
        if handle == invalid_handle:
            error_code = ctypes.get_last_error()
            if error_code in (error_file_not_found, error_path_not_found):
                # entry vanished between the walk and the open; a gone file
                # cannot block a move
                continue
            detail = ctypes.FormatError(error_code).strip()
            if error_code == error_sharing_violation:
                return False, f"not movable: a raw handle holds {path}: {detail}"
            return False, f"not movable: {path}: {detail}"
        if not close_handle(handle):
            logger.warning(
                "Could not close move-probe handle: winerror %d",
                ctypes.get_last_error(),
            )

    return True, "movable snapshot: no incompatible open handles found"


def report_markdown(root: Path, holders: list[LockHolder]) -> str:
    """Markdown table of the current scan, shaped for pasting into Discord."""
    lines = [
        f"**Lock holders under `{_escape_report_text(root)}`** ({len(holders)} found)",
        "",
        "| PID | Name | Locks via | Locked path | Started |",
        "|---|---|---|---|---|",
    ]
    for h in holders:
        started = h.started.strftime("%Y-%m-%d %H:%M") if h.started else "?"
        lines.append(
            f"| {h.pid} | {_escape_report_text(h.name)} | "
            f"{_escape_report_text(h.reason_summary)} | "
            f"`{_escape_report_text(h.locked_paths)}` | {started} |"
        )
    return "\n".join(lines) + "\n"
