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
                "clientInfo": {"name": "deep-aerotwin-unreal-exec", "version": "1.0"},
            },
        },
        timeout=timeout,
    )
    session_id = headers.get("Mcp-Session-Id")
    if not session_id:
        raise RuntimeError("MCP initialize did not return Mcp-Session-Id: %s" % body)
    return session_id


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
    text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
    if bool(result.get("isError")):
        raise RuntimeError(text)

    match = re.search(r"\{.*\}\s*$", text, re.DOTALL)
    if not match:
        return text
    wrapper = json.loads(match.group(0))
    output = wrapper.get("output", "")
    error = wrapper.get("error", "")
    if error:
        raise RuntimeError(error + ("\n" + output if output else ""))
    return output


def main():
    parser = argparse.ArgumentParser(description="Execute Python in the open Unreal Editor through the MCP Automation Bridge.")
    parser.add_argument("script", nargs="?", help="Python script path. Reads stdin when omitted.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    if args.script:
        code = pathlib.Path(args.script).read_text(encoding="utf-8")
    else:
        code = sys.stdin.read()
    session_id = initialize(args.mcp_url, args.timeout)
    output = parse_sse_tool_result(call_execute_python(args.mcp_url, session_id, code, args.timeout))
    print(output, end="" if str(output).endswith("\n") else "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(1)
