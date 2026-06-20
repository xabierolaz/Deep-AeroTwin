#!/usr/bin/env python3
"""
tee.py - TCP Log Client
=======================
- Reads stdin
- Prints to local STDOUT (with cap)
- Sends to Log Server (TCP 9090)
"""
import sys
import socket
import argparse
import os
import time
from constants import LOG_SERVER_HOST, LOG_SERVER_PORT, TEE_CAP_LINES, TEE_PREFIX_DEFAULT

LOG_HOST = str(LOG_SERVER_HOST)
LOG_PORT = int(LOG_SERVER_PORT)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default=str(TEE_PREFIX_DEFAULT), help="Log prefix (e.g., BRAIN)")
    parser.add_argument("--cap-lines", type=int, default=int(TEE_CAP_LINES), help="Max lines local terminal")
    parser.add_argument(
        "--repeat-summary-interval",
        type=float,
        default=float(os.environ.get("PORCE_TEE_REPEAT_SUMMARY_INTERVAL_S", "10.0")),
        help="Seconds between summaries for repeated identical lines; 0 disables suppression.",
    )
    args, _ = parser.parse_known_args()

    # Intentar conectar al servidor de logs
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connected = False
    try:
        sock.connect((LOG_HOST, LOG_PORT))
        connected = True
    except ConnectionRefusedError:
        # Si el servidor no esta arriba, seguimos funcionando solo con salida local
        sys.stderr.write(f"[TEE WARNING] Log Server not found at {LOG_HOST}:{LOG_PORT}. Logging locally only.\n")

    line_count = 0
    repeat_interval_s = max(0.0, float(args.repeat_summary_interval))
    last_clean_line = None
    repeated_count = 0
    last_repeat_summary_ts = time.monotonic()

    def emit(clean_line: str, local_line: str | None = None) -> None:
        nonlocal connected, line_count
        if local_line is None:
            local_line = clean_line + "\n"

        if connected:
            try:
                payload = f"[{args.prefix}] {clean_line}\n"
                sock.sendall(payload.encode('utf-8'))
            except Exception:
                connected = False
                sys.stderr.write("[TEE] Log Server disconnected.\n")

        if args.cap_lines == 0 or line_count < args.cap_lines:
            sys.stdout.write(local_line)
            sys.stdout.flush()
            line_count += 1
        elif line_count == args.cap_lines:
            sys.stdout.write(f"--- Local terminal output paused (See Master Log) ---\n")
            sys.stdout.flush()
            line_count += 1

    def emit_repeat_summary(force: bool = False) -> None:
        nonlocal repeated_count, last_repeat_summary_ts
        if repeated_count <= 0 or not last_clean_line:
            return
        now = time.monotonic()
        if force or repeat_interval_s <= 0.0 or (now - last_repeat_summary_ts) >= repeat_interval_s:
            sample = last_clean_line
            if len(sample) > 180:
                sample = sample[:177] + "..."
            emit(f"[TEE] suppressed {repeated_count} repeated identical lines: {sample}")
            repeated_count = 0
            last_repeat_summary_ts = now
    
    try:
        for line in sys.stdin:
            clean_line = line.rstrip()
            if not clean_line: continue

            if repeat_interval_s > 0.0 and clean_line == last_clean_line:
                repeated_count += 1
                emit_repeat_summary(False)
                continue

            emit_repeat_summary(True)
            last_clean_line = clean_line
            repeated_count = 0
            last_repeat_summary_ts = time.monotonic()
            emit(clean_line, line)

    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass
    finally:
        emit_repeat_summary(True)
        if connected:
            sock.close()

if __name__ == '__main__':
    main()
