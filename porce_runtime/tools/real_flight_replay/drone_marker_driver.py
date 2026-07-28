#!/usr/bin/env python3
"""Driver del marcador del dron en Unreal durante el replay (Pipeline B).

Mueve BP_AirplaneMarker (el anclado al inicio del vuelo real, en el origen)
siguiendo la telemetria real que el Brain publica en /api/ui/data (world_m NED).
Mapeo NED->UE: X=North*100, Y=East*100, Z=Up*100 (cm), yaw=rumbo.

El marcador reproduce EXACTAMENTE el vuelo del video, sincronizado con los
frames que la vision procesa (la misma pose alimenta ambos).

Uso:
  python drone_marker_driver.py [--brain http://127.0.0.1:8080] [--token X]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import requests

MCP_URL = "http://127.0.0.1:3000/mcp"
MARKER_LABEL = "BP_AirplaneMarker"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PY_GET = '''
import unreal, json
out = {"found": []}
try:
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    for a in unreal.GameplayStatics.get_all_actors_of_class(pie, unreal.Actor):
        try:
            lbl = a.get_actor_label()
        except Exception:
            lbl = a.get_name()
        if lbl == "@LABEL@":
            loc = a.get_actor_location()
            out["found"].append({"x": loc.x, "y": loc.y, "z": loc.z})
except Exception as e:
    out["error"] = str(e)
print("JSONOUT:" + json.dumps(out))
'''

PY_SET = '''
import unreal, json
done = False
err = ""
try:
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    for a in unreal.GameplayStatics.get_all_actors_of_class(pie, unreal.Actor):
        try:
            lbl = a.get_actor_label()
        except Exception:
            lbl = a.get_name()
        if lbl == "@LABEL@":
            a.set_actor_location(unreal.Vector(%(X)f, %(Y)f, %(Z)f), False, False)
            a.set_actor_rotation(unreal.Rotator(0.0, %(YAW)f, 0.0), False)
            done = True
            break
except Exception as e:
    err = str(e)
print("JSONOUT:" + json.dumps({"done": done, "err": err}))
'''

PY_COUNT_PROXIES = '''
import unreal, json
out = {"proxies": 0, "tagged": 0}
try:
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    n = 0
    for a in unreal.GameplayStatics.get_all_actors_of_class(pie, unreal.Actor):
        try:
            cls = a.get_class().get_name()
        except Exception:
            cls = ""
        if "SemanticProxy" in cls:
            n += 1
    out["proxies"] = n
except Exception as e:
    out["error"] = str(e)
print("JSONOUT:" + json.dumps(out))
'''


def mcp_initialize(timeout=30):
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "drone-marker-driver", "version": "1.0"}},
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers.get("Mcp-Session-Id")


def mcp_python(session_id: str, code: str, timeout=30):
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                         "params": {"name": "system_control",
                                    "arguments": {"action": "execute_python", "code": code}}}).encode(),
        headers={"Content-Type": "application/json", "Mcp-Session-Id": session_id,
                 "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
    text = ""
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        result = data.get("result")
        if result:
            text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
    text_u = text.replace('\\"', '"').replace("\\n", "\n")
    i = text_u.find("JSONOUT:")
    if i >= 0:
        j = text_u.find("{", i)
        if j >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(text_u, j)
                return obj
            except json.JSONDecodeError:
                return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", default="http://127.0.0.1:8080")
    ap.add_argument("--token", default="")
    ap.add_argument("--rate-hz", type=float, default=6.0)
    ap.add_argument("--log-path", default=str(Path(__file__).resolve().parent / "out" / "flight_path_log.jsonl"),
                    help="JSONL con posiciones comandadas y leidas del marcador")
    args = ap.parse_args()

    log_file = Path(args.log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fp = log_file.open("w", encoding="utf-8")

    headers = {"X-PORCE-Token": args.token} if args.token else {}
    sess_http = requests.Session()
    print("[driver] esperando Brain y MCP...")
    for _ in range(60):
        try:
            r = sess_http.get(f"{args.brain}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1.0)
    session_id = None
    for _ in range(90):
        try:
            session_id = mcp_initialize(timeout=2)
            if session_id:
                break
        except Exception:
            time.sleep(1.0)
    if not session_id:
        raise SystemExit("MCP no disponible")

    base = None
    for _ in range(30):
        out = mcp_python(session_id, PY_GET.replace("@LABEL@", MARKER_LABEL), timeout=5)
        if out and out.get("found"):
            f = out["found"][0]
            base = (float(f["x"]), float(f["y"]), float(f["z"]))
            break
        time.sleep(1.0)
    if not base:
        raise SystemExit("marcador no encontrado en PIE")
    print(f"[driver] base marcador: ({base[0]:.0f}, {base[1]:.0f}, {base[2]:.0f}) cm")

    period = 1.0 / max(0.5, args.rate_hz)
    last_ts = 0.0
    stale = 0
    tick = 0
    while True:
        t0 = time.perf_counter()
        try:
            r = sess_http.get(f"{args.brain}/api/ui/data", headers=headers, timeout=1.0)
            data = r.json()
            tel = data.get("telemetry", {}) or {}
            wm = tel.get("world_m") or {}
            ts = float(tel.get("last_update", 0.0) or 0.0)
            if wm and ts != last_ts:
                north = float(wm.get("north", 0.0) or 0.0)
                east = float(wm.get("east", 0.0) or 0.0)
                up = float(wm.get("up", 0.0) or 0.0)
                yaw = float(tel.get("heading", tel.get("yaw", 0.0)) or 0.0)
                code = (PY_SET % {
                    "X": base[0] + north * 100.0,
                    "Y": base[1] + east * 100.0,
                    "Z": base[2] + up * 100.0,
                    "YAW": yaw,
                }).replace("@LABEL@", MARKER_LABEL)
                res = mcp_python(session_id, code, timeout=5)
                if res is not None and not res.get("done", True) and tick % 30 == 0:
                    print(f"[driver] aviso: set fallo: {res.get('err', '?')}")
                log_fp.write(json.dumps({
                    "t": time.time(), "type": "cmd",
                    "north": north, "east": east, "up": up, "yaw": yaw,
                }) + "\n")
                log_fp.flush()
                last_ts = ts
                stale = 0
                tick += 1
                if tick % 15 == 0:
                    rb = mcp_python(session_id, PY_GET.replace("@LABEL@", MARKER_LABEL), timeout=5)
                    if rb and rb.get("found"):
                        f = rb["found"][0]
                        log_fp.write(json.dumps({
                            "t": time.time(), "type": "readback",
                            "x": f["x"], "y": f["y"], "z": f["z"],
                        }) + "\n")
                        log_fp.flush()
                if tick % 30 == 0:
                    nobs = len(data.get("obstacles", []) or [])
                    proxies = mcp_python(session_id, PY_COUNT_PROXIES, timeout=5)
                    print(f"[driver] t+{tick}: dron N{north:.0f} E{east:.0f} U{up:.0f} yaw{yaw:.0f} | obs brain={nobs} proxies UE={(proxies or {}).get('proxies')}")
            else:
                stale += 1
        except Exception as e:
            stale += 1
            if stale % 20 == 0:
                print(f"[driver] aviso: {type(e).__name__}: {e}")
        if stale > int(45 * args.rate_hz):
            print("[driver] telemetria sin actualizar >45 s; fin del replay. Saliendo.")
            break
        dt = time.perf_counter() - t0
        if dt < period:
            time.sleep(period - dt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
