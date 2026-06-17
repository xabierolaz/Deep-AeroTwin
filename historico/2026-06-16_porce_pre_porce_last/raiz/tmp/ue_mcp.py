#!/usr/bin/env python3
"""Minimal client for the McpAutomationBridge HTTP MCP endpoint (port 3000).

Usage:
  python ue_mcp.py <tool> <json-arguments> [--out FILE]
  python ue_mcp.py system_control "{\"action\":\"execute_python\",\"command\":\"print('hi')\"}"
"""

import argparse
import json
import sys
import urllib.request

URL = "http://127.0.0.1:3000/mcp"


def rpc(payload: dict, session: str | None = None) -> tuple[dict | None, str | None]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if session:
        req.add_header("Mcp-Session-Id", session)
    with urllib.request.urlopen(req, timeout=120) as resp:
        new_session = resp.headers.get("Mcp-Session-Id")
        body = resp.read().decode("utf-8", errors="replace")
    # Parse SSE or plain JSON
    if body.lstrip().startswith("{"):
        return json.loads(body), new_session
    result = None
    for line in body.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if not chunk:
                continue
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                result = obj
    return result, new_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="?", default=None)
    parser.add_argument("--args-file", default=None, help="file with JSON arguments")
    parser.add_argument("--exec-python", default=None, help="editor python file -> system_control execute_python")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.exec_python:
        source = open(args.exec_python, encoding="utf-8").read()
        args.tool = "system_control"
        args.arguments = json.dumps({"action": "execute_python", "code": source})
    elif args.args_file:
        args.arguments = open(args.args_file, encoding="utf-8").read()
    if args.arguments is None:
        print("missing arguments", file=sys.stderr)
        return 2

    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "cowork-audit-driver", "version": "1.0"},
        },
    }
    _, session = rpc(init)
    rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)

    call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": args.tool, "arguments": json.loads(args.arguments)},
    }
    result, _ = rpc(call, session)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    print(text[:4000])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback

        with open(r"D:\Deep-AeroTwin-UE57-Test\tmp\ue_mcp_lasterror.txt", "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        sys.exit(1)
