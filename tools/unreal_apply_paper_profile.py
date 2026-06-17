import argparse
import json
import pathlib
import re
import sys
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
UNREAL_SCRIPT = ROOT / "Unreal" / "Scripts" / "paper_scenario_visibility.py"
DEFAULT_MCP_URL = "http://127.0.0.1:3000/mcp"


def post_mcp(url, payload, session_id=None, accept=None, timeout=120):
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, dict(response.headers), response.read().decode("utf-8", "replace")


def initialize(url, timeout):
    _, headers, body = post_mcp(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "deep-aerotwin-paper-profile", "version": "1.0"},
            },
        },
        timeout=timeout,
    )
    session_id = headers.get("Mcp-Session-Id")
    if not session_id:
        raise RuntimeError("MCP initialize did not return Mcp-Session-Id: %s" % body)
    return session_id


def build_unreal_code(args):
    source = UNREAL_SCRIPT.read_text(encoding="utf-8")
    if args.list_profiles:
        action = "list"
        profile = ""
    elif args.describe:
        action = "describe"
        profile = ""
    else:
        action = "apply"
        profile = args.profile

    return (
        "import json\n"
        "_PAPER_AUTO_RUN = True\n"
        "_PAPER_ACTION = %r\n"
        "_PAPER_PROFILE_NAME = %r\n"
        "_PAPER_DRY_RUN = %r\n"
        "_PAPER_INCLUDE_DETAILS = %r\n"
        "_PAPER_INCLUDE_ACTORS = %r\n"
        "_PAPER_INCLUDE_UNCLASSIFIED = %r\n"
        "exec(%r)\n"
    ) % (
        action,
        profile,
        bool(args.dry_run),
        bool(args.details),
        bool(args.actors or args.details),
        bool(args.include_unclassified),
        source,
    )


def call_execute_python(url, session_id, code, timeout):
    _, _, body = post_mcp(
        url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "system_control",
                "arguments": {"action": "execute_python", "code": code},
            },
        },
        session_id=session_id,
        accept="text/event-stream",
        timeout=timeout,
    )
    return body


def parse_sse_tool_result(body):
    final_payload = None
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if "id" in data and "result" in data:
            final_payload = data
    if final_payload is None:
        raise RuntimeError("No final MCP tool result found in SSE body:\n%s" % body)

    result = final_payload["result"]
    is_error = bool(result.get("isError"))
    text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
    if is_error:
        raise RuntimeError(text)

    match = re.search(r"\{.*\}\s*$", text, re.DOTALL)
    if not match:
        return {"raw_text": text}
    wrapper = json.loads(match.group(0))
    output = wrapper.get("output", "")
    error = wrapper.get("error", "")
    if error:
        return {"error": error, "output": output}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"output": output}


def main():
    parser = argparse.ArgumentParser(description="Apply Deep-AeroTwin paper visibility profiles in the open Unreal Editor.")
    parser.add_argument("--profile", default="paper_all_obstacles", help="Profile to apply.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without modifying Unreal visibility.")
    parser.add_argument("--details", action="store_true", help="Include component-level changes in the output.")
    parser.add_argument("--actors", action="store_true", help="Include per-actor rows in apply/describe output.")
    parser.add_argument("--describe", action="store_true", help="Describe current controlled scene groups.")
    parser.add_argument("--list-profiles", action="store_true", help="List available profiles.")
    parser.add_argument("--include-unclassified", action="store_true", help="Include unclassified actors in --describe output.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL, help="Native MCP endpoint URL.")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    if not UNREAL_SCRIPT.exists():
        raise FileNotFoundError(UNREAL_SCRIPT)

    session_id = initialize(args.mcp_url, args.timeout)
    body = call_execute_python(args.mcp_url, session_id, build_unreal_code(args), args.timeout)
    print(json.dumps(parse_sse_tool_result(body), indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(1)
