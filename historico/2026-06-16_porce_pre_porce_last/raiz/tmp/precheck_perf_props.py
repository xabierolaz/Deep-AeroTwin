import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\perf_props.json"
out = {}
for cls_path in [
    "/Script/UnrealEd.EditorPerformanceSettings",
    "/Script/UnrealEd.LevelEditorPlaySettings",
]:
    try:
        cls = unreal.load_class(None, cls_path)
        cdo = unreal.get_default_object(cls)
        props = []
        for line in str(cdo.__doc__ or "").splitlines():
            line = line.strip()
            if line.startswith("``"):
                props.append(line.split("``")[1])
        # fallback: dir()
        if not props:
            props = [p for p in dir(cdo) if not p.startswith("_")]
        out[cls_path] = props
    except Exception as exc:
        out[cls_path] = f"error: {exc}"

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("PERF_PROPS_DONE")
