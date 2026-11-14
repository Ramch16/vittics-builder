"""What differs on Windows: which shell runs commands, and how CLIs are started safely.

Commands (product checks, deploy and health commands, agents' run_command) are written for a POSIX
shell. On Windows they run in Git Bash, which comes with Git for Windows; WSL's bash.exe is skipped
because it runs in a different system. Without Git Bash they fall back to cmd.exe.

npm installs CLIs on Windows as .cmd wrappers, and cmd.exe re-reads their arguments: `&`, `|`, `%`
and quotes in a prompt could run other commands ("BatBadBut"). So an npm wrapper is bypassed by
running its Node script directly, and any other .cmd/.bat is refused when an argument contains
characters cmd.exe would interpret.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

WINDOWS = os.name == "nt"
CMD_UNSAFE = re.compile(r'[\r\n"&|<>^%!()]')
NPM_SHIM = re.compile(r'"%(?:dp0|~dp0)%\\([^"]+?\.(?:js|cjs|mjs))"', re.I)


class UnsafeCommand(RuntimeError):
    pass


def git_bash() -> str | None:
    """Git for Windows' bash.exe, if installed (never WSL's)."""
    if os.environ.get("VITTICS_BASH"):
        return os.environ["VITTICS_BASH"]
    git = shutil.which("git")
    if not git:
        return None
    for parent in Path(git).resolve().parents:
        for candidate in (parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe"):
            if candidate.is_file() and "system32" not in str(candidate).lower():
                return str(candidate)
    return None


def shell_command(command: str) -> tuple[list[str] | str, bool]:
    """(args, shell) for subprocess.run: sh on macOS/Linux, Git Bash (else cmd.exe) on Windows."""
    if not WINDOWS:
        return command, True
    bash = git_bash()
    return ([bash, "-lc", command], False) if bash else (command, True)


def unshim(path: str) -> list[str] | None:
    """The Node script behind an npm .cmd wrapper, as [node, script]."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = NPM_SHIM.search(text)
    node = shutil.which("node")
    if not m or not node:
        return None
    script = (Path(path).parent / m.group(1).replace("\\", os.sep)).resolve()
    return [node, str(script)] if script.is_file() else None


def safe_argv(argv: list[str]) -> list[str]:
    """How to start a CLI without letting cmd.exe re-read its arguments."""
    if not WINDOWS or not argv:
        return argv
    exe = shutil.which(argv[0]) or argv[0]
    if not exe.lower().endswith((".cmd", ".bat")):
        return [exe, *argv[1:]]
    direct = unshim(exe)
    if direct:
        return direct + argv[1:]
    if any(CMD_UNSAFE.search(a) for a in argv[1:]):
        raise UnsafeCommand(f"{Path(exe).name} is a Windows batch wrapper and its arguments contain characters cmd.exe "
                            "would treat as commands. Install the CLI's native .exe, or run it from WSL.")
    return [exe, *argv[1:]]


def keep_awake(enabled: bool = True) -> str:
    """Stop this computer from sleeping while this process runs, so agents' work is not frozen overnight.
    Returns how ('caffeinate', 'SetThreadExecutionState') or '' when it is off or unsupported."""
    if not enabled:
        return ""
    import subprocess
    import sys
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        # -i idle sleep, -m disk sleep, -s system sleep on power; -w ends it when this process exits
        subprocess.Popen(["caffeinate", "-ims", "-w", str(os.getpid())], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "caffeinate"
    if os.name == "nt":
        import ctypes
        es_continuous, es_system_required = 0x80000000, 0x00000001    # kept until this thread exits
        if ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required):
            return "SetThreadExecutionState"
    return ""


def rmtree_force(path) -> None:
    """Remove a folder tree, read-only files included: git makes its object files read-only, and Windows refuses to
    delete those until they are made writable."""
    import stat
    import sys

    def retry(function, target, _error) -> None:
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            function(target)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)



def pid_alive(pid: int | None) -> bool:
    """Is this process still running? Never signals it: on Windows os.kill(pid, 0) terminates the process."""
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, 0, int(pid))              # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5                        # access denied: it exists, it is not ours
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                              # it exists; it just is not ours
    except OSError:
        return False
    return True


def kill_descendants() -> int:
    """Stop every process this one started and has not reaped (agents' CLIs, previews). Used as the app quits, so a
    closed window does not leave an agent working on its own. Returns how many were stopped."""
    import signal
    import subprocess
    me = os.getpid()
    if os.name == "nt":                          # ends this process too: only call it as the app is exiting
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(me)], capture_output=True)
        return 0
    try:
        table = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    children: dict[int, list[int]] = {}
    for line in table.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, queue = [], list(children.get(me, []))
    while queue:
        pid = queue.pop()
        found.append(pid)
        queue.extend(children.get(pid, []))
    for pid in found:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    return len(found)
