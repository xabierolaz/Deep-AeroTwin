"""
Run ArduPilot SITL through WSL and forward output to the PORCE log server.

This avoids `cmd.exe` pipelines around wsl.exe, which can emit noisy stdin
redirection warnings in Windows Terminal tabs.
"""

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

from constants import LOG_SERVER_HOST, LOG_SERVER_PORT, TEE_CAP_LINES


def _connect_log_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((str(LOG_SERVER_HOST), int(LOG_SERVER_PORT)))
        return sock
    except ConnectionRefusedError:
        sys.stderr.write(
            f"[SITL_RUNNER WARNING] Log Server not found at {LOG_SERVER_HOST}:{LOG_SERVER_PORT}. "
            "Logging locally only.\n"
        )
        sock.close()
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="SITL")
    parser.add_argument("--cap-lines", type=int, default=int(TEE_CAP_LINES))
    args = parser.parse_args()

    pipeline_dir = Path(__file__).resolve().parent
    cmd = ["wsl", "--cd", str(pipeline_dir), "--exec", "bash", "run_sitl.sh"]
    sock = _connect_log_server()
    local_count = 0

    def emit(line: str) -> None:
        nonlocal sock, local_count
        clean = line.rstrip()
        if not clean:
            return
        if sock is not None:
            try:
                sock.sendall(f"[{args.prefix}] {clean}\n".encode("utf-8"))
            except Exception:
                sock.close()
                sock = None
                sys.stderr.write("[SITL_RUNNER] Log Server disconnected.\n")

        if args.cap_lines == 0 or local_count < args.cap_lines:
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
            sys.stdout.flush()
            local_count += 1
        elif local_count == args.cap_lines:
            sys.stdout.write("--- Local terminal output paused (See Master Log) ---\n")
            sys.stdout.flush()
            local_count += 1

    try:
        stdin_handle = None
        try:
            # WSL emits "Input redirection is not supported" if it inherits a
            # non-console stdin from a launcher wrapper. Prefer the real console.
            stdin_handle = open("CONIN$", "r")
        except OSError:
            stdin_handle = None
        proc = subprocess.Popen(
            cmd,
            cwd=str(pipeline_dir),
            stdin=stdin_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
    except FileNotFoundError:
        emit("[ERROR] wsl.exe not found in PATH")
        return 127

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            emit(line)
        return int(proc.wait())
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        return 130
    finally:
        try:
            if stdin_handle is not None:
                stdin_handle.close()
        except Exception:
            pass
        if sock is not None:
            sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
