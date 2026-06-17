import unreal

results = []
cls = unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")
cdo = unreal.get_default_object(cls)
for name in ["bThrottleCPUWhenNotForeground", "ThrottleCPUWhenNotForeground"]:
    try:
        cdo.set_editor_property(name, False)
        results.append(f"{name}: OK")
        break
    except Exception as exc:
        results.append(f"{name}: {exc}")
try:
    cdo.call_method("PostEditChange")
except Exception:
    pass
# also try the engine-level idle cvar
try:
    unreal.SystemLibrary.execute_console_command(None, "t.IdleWhenNotForeground 0")
    results.append("cvar t.IdleWhenNotForeground 0: OK")
except Exception as exc:
    results.append(f"cvar: {exc}")
print("THROTTLE2 " + " | ".join(results))
with open(r"D:\Deep-AeroTwin-UE57-Test\tmp\throttle2.txt", "w") as fh:
    fh.write("\n".join(results))
