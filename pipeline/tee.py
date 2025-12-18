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
import time

LOG_HOST = '127.0.0.1'
LOG_PORT = 9090

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="UNK", help="Log prefix (e.g., BRAIN)")
    parser.add_argument("--cap-lines", type=int, default=200, help="Max lines local terminal")
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
    
    try:
        for line in sys.stdin:
            clean_line = line.rstrip()
            if not clean_line: continue

            # 1. Enviar a Servidor (Red)
            if connected:
                try:
                    # Formato: [PREFIX] Mensaje
                    payload = f"[{args.prefix}] {clean_line}\n"
                    sock.sendall(payload.encode('utf-8'))
                except Exception:
                    connected = False # Se cayo el servidor
                    sys.stderr.write("[TEE] Log Server disconnected.\n")

            # 2. Imprimir Localmente (Terminal)
            if args.cap_lines == 0 or line_count < args.cap_lines:
                sys.stdout.write(line) # line ya tiene \n
                sys.stdout.flush()
                line_count += 1
            elif line_count == args.cap_lines:
                sys.stdout.write(f"--- Local terminal output paused (See Master Log) ---\n")
                sys.stdout.flush()
                line_count += 1

    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass
    finally:
        if connected:
            sock.close()

if __name__ == '__main__':
    main()
