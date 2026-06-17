import ast, sys, py_compile

target = r"D:\Deep-AeroTwin-UE57-Test\pipeline\flight_controller.py"
out = r"D:\Deep-AeroTwin-UE57-Test\tmp\d3_check_result.txt"

lines = []
try:
    src = open(target, encoding="utf-8").read()
    ast.parse(src)
    lines.append("AST OK")
    py_compile.compile(target, doraise=True)
    lines.append("PYCOMPILE OK")
    lines.append(f"planner_obs_ids occurrences: {src.count('planner_obs_ids')}")
except Exception as e:
    lines.append(f"FAIL: {type(e).__name__}: {e}")
lines.append(f"python: {sys.version}")
open(out, "w", encoding="utf-8").write("\n".join(lines))
