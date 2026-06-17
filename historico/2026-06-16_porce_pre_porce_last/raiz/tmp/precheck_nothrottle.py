import unreal

try:
    cls = unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")
    s = unreal.get_default_object(cls)
    s.set_editor_property("throttle_cpu_when_not_foreground", False)
    print("THROTTLE_OFF ok")
except Exception as exc:
    print(f"THROTTLE_OFF error: {exc}")
