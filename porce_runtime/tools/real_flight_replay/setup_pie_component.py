"""Inyecta/configura el ReplayTwinManager+componente en el PIE en marcha (Pipeline B).

Idempotente: si el manager no tiene componente PorceTelemetry, lo crea;
en cualquier caso fija config y habilita el tick (poll 5 Hz del Brain).

Uso: python setup_pie_component.py [--token X]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

MCP_URL = "http://127.0.0.1:3000/mcp"
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CODE = r'''
import unreal, json
out = {"created": False, "configured": False, "tick": False}
TOKEN = "__TOKEN__"
try:
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    mgr = None
    for a in unreal.GameplayStatics.get_all_actors_of_class(pie, unreal.Actor):
        try:
            if a.get_actor_label() == "ReplayTwinManager":
                mgr = a
                break
        except Exception:
            pass
    if mgr is not None:
        comps = a.get_components_by_class(unreal.PorceTelemetryComponent) if mgr else []
        if comps:
            comp = comps[0]
        else:
            add = getattr(mgr, "add_component_by_class", None)
            comp = add(unreal.PorceTelemetryComponent, False, unreal.Transform(), False) if add else unreal.new_object(unreal.PorceTelemetryComponent, outer=mgr)
            try:
                comp.register_component()
            except Exception:
                pass
            out["created"] = True
        comp.set_editor_property("bShowSpawnBackendSwitchUI", False)
        comp.set_editor_property("AuthToken", TOKEN)
        comp.set_editor_property("HomeLatDeg", 42.1424624)
        comp.set_editor_property("HomeLonDeg", -1.5888362)
        comp.set_editor_property("OriginActor", mgr)
        setter = getattr(comp, "set_spawn_backend", None)
        enum_cls = getattr(unreal, "PorceTwinSpawnBackend", None)
        if setter and enum_cls:
            for item in list(enum_cls):
                if "PROXY" in str(item).upper() and "INSTANCED" not in str(item).upper():
                    setter(item)
                    break
        comp.set_component_tick_enabled(True)
        out["configured"] = True
        out["tick"] = bool(comp.is_component_tick_enabled())
        out["backend"] = str(comp.get_editor_property("SpawnBackend"))
except Exception as e:
    out["error"] = str(e)
print("JSONOUT:" + json.dumps(out))
'''


def mcp_initialize(timeout=10):
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "setup-pie-component", "version": "1.0"}}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers.get("Mcp-Session-Id")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default="replaym20token1234567890123456")
    ap.add_argument("--retries", type=int, default=60)
    args = ap.parse_args()

    import time
    sid = None
    for _ in range(args.retries):
        try:
            sid = mcp_initialize(timeout=2)
            if sid:
                break
        except Exception:
            time.sleep(1.0)
    if not sid:
        raise SystemExit("MCP no disponible")

    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                         "params": {"name": "system_control",
                                    "arguments": {"action": "execute_python",
                                                  "code": CODE.replace("__TOKEN__", args.token)}}}).encode(),
        headers={"Content-Type": "application/json", "Mcp-Session-Id": sid, "Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", "replace")
    import re
    m = re.search(r"JSONOUT:(\{[^\n]*\})", body.replace('\\"', '"'))
    print(m.group(1) if m else body[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
