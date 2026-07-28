#!/usr/bin/env python3
"""
Log Server - Centralized Logging Hub
====================================
- Listens on LOG_SERVER_HOST:LOG_SERVER_PORT
- Receives logs from multiple processes
- Writes to a shared log file (thread-safe)
- Prints aggregated output to stdout
"""

import datetime
import os
import socket
import sys
import threading
import time

from constants import (
    LOG_SERVER_HOST,
    LOG_SERVER_LISTEN_HOST,
    LOG_SERVER_PORT,
    TEE_PREFIX_DEFAULT,
    LOG_SERVER_DEDUPE_INTERVAL_S,
    LOG_SERVER_FILE,
    LOG_SERVER_RECV_BUFFER_BYTES,
)

DEDUPE_INTERVAL = max(0.0, float(LOG_SERVER_DEDUPE_INTERVAL_S))
LOG_PORT = int(LOG_SERVER_PORT)
LOG_HOST_BIND = str(LOG_SERVER_LISTEN_HOST)
LOG_FILE = str(LOG_SERVER_FILE)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.isabs(LOG_FILE):
    LOG_FILE = os.path.join(SCRIPT_DIR, LOG_FILE)

io_lock = threading.Lock()


def handle_client(conn: socket.socket, _addr: tuple[str, int]) -> None:
    buffer = ""
    try:
        while True:
            data = conn.recv(int(LOG_SERVER_RECV_BUFFER_BYTES))
            if not data:
                break

            text = data.decode("utf-8", errors="replace")
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                process_log_line(line)
    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"[SERVER ERROR] {e}")
    finally:
        conn.close()


last_message_content = {}


def process_log_line(line: str) -> None:
    prefix = str(TEE_PREFIX_DEFAULT)
    content = line

    if line.startswith("[") and "]" in line:
        try:
            prefix_end = line.find("]")
            prefix = line[1:prefix_end]
            content = line[prefix_end + 1 :].strip()
        except Exception:
            pass

    now_ts = time.time()
    prev = last_message_content.get(prefix)
    if prev is not None:
        prev_content, prev_ts = prev
        if content == prev_content and (now_ts - float(prev_ts)) < DEDUPE_INTERVAL:
            return

    last_message_content[prefix] = (content, now_ts)
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    final_line = f"[{now_str}] {line}\n"

    with io_lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(final_line)
        except Exception as e:
            print(f"[FILE ERROR] {e}")

        sys.stdout.write(final_line)
        sys.stdout.flush()


def main() -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== SYSTEM LOG STARTED {datetime.datetime.now()} ===\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((LOG_HOST_BIND, LOG_PORT))
        server.listen(5)
        print("==========================================")
        print(f" LOG SERVER LISTENING ON {LOG_HOST_BIND}:{LOG_PORT}")
        print(f" LOG SERVER CLIENT EXPECTED ON {LOG_SERVER_HOST}:{LOG_PORT}")
        print(f" Writing to: {LOG_FILE}")
        print("==========================================")

        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopping...")
    except Exception as e:
        print(f"\n[SERVER CRITICAL] {e}")
    finally:
        server.close()


if __name__ == "__main__":
    main()
