import unreal

cls = unreal.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings")
cdo = unreal.get_default_object(cls)
results = []
for value in ["PlayInEditorFloating", "PIE_StandaloneWithPreview", 1]:
    try:
        cdo.set_editor_property("LastExecutedPlayModeType", value)
        results.append(f"set {value!r}: OK -> {cdo.get_editor_property('LastExecutedPlayModeType')}")
        break
    except Exception as exc:
        results.append(f"set {value!r}: {str(exc)[:160]}")
try:
    results.append("current: " + str(cdo.get_editor_property("LastExecutedPlayModeType")))
except Exception as exc:
    results.append("get failed: " + str(exc)[:120])
with open(r"D:\Deep-AeroTwin-UE57-Test\tmp\set_pie_floating.txt", "w") as fh:
    fh.write("\n".join(results))
print(" | ".join(results))
