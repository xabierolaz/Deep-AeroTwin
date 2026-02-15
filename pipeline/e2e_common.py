from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]


def popen(
    args: list[str],
    *,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[Path] = None,
    stdout_path: Optional[Path] = None,
) -> subprocess.Popen:
    stdout_handle = None
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_handle = stdout_path.open("w", encoding="utf-8")

    # New process group so we can terminate child processes on timeout.
    return subprocess.Popen(
        args,
        env=env,
        cwd=str(cwd or REPO_ROOT),
        stdout=stdout_handle or subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=(stdout_handle is None),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )


def kill_proc(proc: subprocess.Popen, name: str) -> None:
    del name
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def wslpath(win_path: Path) -> str:
    # `wsl wslpath -u` can mis-handle backslashes; pass a D:/... style path.
    win_arg = str(win_path).replace("\\", "/")
    try:
        out = subprocess.check_output(
            ["wsl", "wslpath", "-u", win_arg],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except FileNotFoundError as e:
        raise RuntimeError("wsl_not_found: Pipeline A requires WSL2 (wsl.exe).") from e
    except subprocess.CalledProcessError as e:
        msg = (e.output or str(e)).strip()
        raise RuntimeError(
            "wsl_failed: could not run `wsl wslpath -u ...`.\n"
            f"details: {msg}\n"
            "hint: verify WSL works in a normal terminal (try `wsl -l -v`)."
        ) from e
    if not out:
        raise RuntimeError(f"wslpath_empty:{win_path}")
    return out


def wait_http_ok(url: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_err: str = ""
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
            last_err = f"status={r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise TimeoutError(f"http_not_ready:{url}:{last_err}")


def get_status(base_url: str) -> dict:
    r = requests.get(f"{base_url}/api/status", timeout=2)
    r.raise_for_status()
    return r.json()
