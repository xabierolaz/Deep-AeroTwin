#!/usr/bin/env python3
"""
Log Server - Centralized Logging Hub
====================================
- Listens on TCP 9090
- Receives logs from multiple processes
- Writes to logs/SYSTEM_ALL.log (Thread-safe)
- Displays aggregated output to console
"""
import socket
import threading
import os
import datetime
import sys
import time

LOG_PORT = 9090
# Ruta Absoluta basada en la ubicacion de este script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "logs", "SYSTEM_ALL.log")

# Lock para sincronizar escritura en archivo y consola
io_lock = threading.Lock()

def handle_client(conn, addr):
    """Maneja la conexión de un proceso (Brain/Eyes)"""
    buffer = ""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            # Decodificar y manejar fragmentacion de mensajes
            text = data.decode('utf-8', errors='replace')
            buffer += text
            
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                process_log_line(line)
                
    except ConnectionResetError:
        pass # Cliente desconectado abruptamente
    except Exception as e:
        print(f"[SERVER ERROR] {e}")
    finally:
        conn.close()

# Estado para deduplicación
last_message_content = {} # { prefix: (content, timestamp) }
DEDUPE_INTERVAL = 1.0

def process_log_line(line):
    """Procesa una línea de log recibida con deduplicación"""
    # Intentar extraer prefijo para deduplicacion por fuente
    # Formato esperado: "[PREFIX] Mensaje"
    prefix = "UNK"
    content = line
    
    if line.startswith("[") and "]" in line:
        try:
            prefix_end = line.find("]")
            prefix = line[1:prefix_end]
            content = line[prefix_end+1:].strip()
        except:
            pass

    now_ts = time.time()
    
    # Chequeo de duplicados
    if prefix in last_message_content:
        last_content, last_ts = last_message_content[prefix]
        if content == last_content and (now_ts - last_ts) < DEDUPE_INTERVAL:
            return # Ignorar duplicado reciente

    # Actualizar ultimo mensaje
    last_message_content[prefix] = (content, now_ts)

    # Agregar timestamp del servidor para orden cronologico perfecto
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    
    # El cliente (tee.py) ya envia "[PREFIX] Mensaje", nosotros agregamos la hora
    final_line = f"[{now_str}] {line}\n"
    
    with io_lock:
        # 1. Escribir a archivo
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(final_line)
        except Exception as e:
            print(f"[FILE ERROR] {e}")

        # 2. Escribir a consola maestra
        sys.stdout.write(final_line)
        sys.stdout.flush()

def main():
    # Asegurar directorio
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    # Limpiar log anterior al arrancar
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== SYSTEM LOG STARTED {datetime.datetime.now()} ===\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permitir reusar puerto inmediatamente si se reinicia
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Escuchar en todas las interfaces para permitir conexion desde WSL
        server.bind(('0.0.0.0', LOG_PORT))
        server.listen(5)
        print(f"==========================================")
        print(f" LOG SERVER LISTENING ON PORT {LOG_PORT}")
        print(f" Writing to: {LOG_FILE}")
        print(f"==========================================")
        
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

if __name__ == '__main__':
    main()
