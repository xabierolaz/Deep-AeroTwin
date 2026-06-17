import py_compile

out = []
for f in [r"D:\Deep-AeroTwin-UE57-Test\pipeline\vision_system.py",
          r"D:\Deep-AeroTwin-UE57-Test\pipeline\constants.py"]:
    try:
        py_compile.compile(f, doraise=True)
        out.append(f"{f}: OK")
    except Exception as e:
        out.append(f"{f}: FAIL {e}")
open(r"D:\Deep-AeroTwin-UE57-Test\tmp\vision_syntax.txt", "w").write("\n".join(out))
print("\n".join(out))
