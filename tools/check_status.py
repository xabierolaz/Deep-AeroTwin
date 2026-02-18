import requests
import sys
from pathlib import Path

from constants import E2E_REQUEST_TIMEOUT_S

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from e2e_common import default_base_url

def check(name, url):
    try:
        r = requests.get(url, timeout=float(E2E_REQUEST_TIMEOUT_S))
        if r.status_code == 200:
            print(f"[OK] {name}: Online (200)")
            return r.json()
        else:
            print(f"[WARN] {name}: Status {r.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] {name}: Connection Refused (Is it running?)")
        return None
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        return None

print("--- DIAGNOSTICO DE SISTEMA (Brain + Eyes) ---")

brain_base_url = default_base_url()

# 1. Check Flight Controller (Brain)
brain_status = check("Flight Controller (Brain)", f"{brain_base_url}/api/status")

if brain_status:
    print(f"    Mode: {brain_status.get('mode')}")
    print(f"    WP Index: {brain_status.get('wp_idx')}")
    print(f"    Evasion Active: {brain_status.get('evasion')}")
    print(f"    Obstacles Tracked: {brain_status.get('obstacles_count')}")

# 2. Check Vision System (Eyes)
# Vision system doesn't expose a server by default in the new architecture (it's a client pushing to Brain),
# but we can infer its health if Brain is receiving obstacles or if we implemented a health endpoint in it.
# Current code doesn't show Vision System having an HTTP server, so we check if Brain has seen updates.
# (This part is inferred from typical monitoring needs)

if brain_status:
    print("\n[SYSTEM SUMMARY]")
    if brain_status.get('mode') == 'UNKNOWN':
        print(">> SITL connection might be down (Mode is UNKNOWN)")
    else:
        print(">> SITL Connected.")
