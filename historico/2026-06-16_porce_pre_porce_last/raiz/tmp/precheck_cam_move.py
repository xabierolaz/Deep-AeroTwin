"""Move editor viewport to vantage N (set IDX below before each call)."""
import json
import unreal

IDX = 0
data = json.load(open(r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_camera.json"))
v = data["vantages"][IDX]
les = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
les.set_level_viewport_camera_info(
    unreal.Vector(v["loc"]["x"], v["loc"]["y"], v["loc"]["z"]),
    unreal.Rotator(roll=0.0, pitch=v["rot"]["pitch"], yaw=v["rot"]["yaw"]),
)
print(f"MOVED_TO_VANTAGE {IDX}")



