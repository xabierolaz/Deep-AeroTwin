import argparse
import json
import pathlib
import re
import sys
import urllib.request

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
                "clientInfo": {"name": "deep-aerotwin-unreal-mcp-call", "version": "1.0"},
            },
        },
        timeout=timeout,
    )
    session_id = headers.get("Mcp-Session-Id")
    if not session_id:
        raise RuntimeError("MCP initialize did not return Mcp-Session-Id: %s" % body)
    return session_id


def parse_tool_result(body):
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
    text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
    if bool(result.get("isError")):
        raise RuntimeError(text)

    match = re.search(r"\{.*\}\s*$", text, re.DOTALL)
    if not match:
        return {"raw_text": text}
    wrapper = json.loads(match.group(0))
    if "output" not in wrapper and "error" not in wrapper:
        return wrapper
    output = wrapper.get("output", "")
    error = wrapper.get("error", "")
    if error:
        raise RuntimeError(error + ("\n" + output if output else ""))
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"output": output}


def parse_scalar(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def set_dotted(target, dotted_key, value):
    cursor = target
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def load_arguments(raw_argument, arg_items):
    if raw_argument == "-":
        payload = json.loads(sys.stdin.read() or "{}")
    elif raw_argument.startswith("@"):
        payload = json.loads(pathlib.Path(raw_argument[1:]).read_text(encoding="utf-8"))
    else:
        payload = json.loads(raw_argument)

    for item in arg_items:
        if "=" not in item:
            raise ValueError("--arg values must use key=value form: %s" % item)
        key, value = item.split("=", 1)
        set_dotted(payload, key, parse_scalar(value))
    return payload


def main():
    parser = argparse.ArgumentParser(description="Call any tool on the open Unreal MCP Automation Bridge.")
    parser.add_argument("tool", help="MCP tool name, e.g. control_editor.")
    parser.add_argument("arguments", nargs="?", default="{}", help="Tool arguments as JSON.")
    parser.add_argument("--arg", action="append", default=[], help="Set one argument as key=value; dotted keys create objects.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--raw", action="store_true", help="Print raw SSE body instead of parsing the tool result.")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    tool_args = load_arguments(args.arguments, args.arg)
    session_id = initialize(args.mcp_url, args.timeout)
    _, _, body = post_mcp(
        args.mcp_url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": args.tool, "arguments": tool_args},
        },
        session_id=session_id,
        accept="text/event-stream",
        timeout=args.timeout,
    )
    if args.raw:
        print(body)
    else:
        print(json.dumps(parse_tool_result(body), indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(1)
