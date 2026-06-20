import json

import unreal


CVARS = {
    "r.Streaming.PoolSize": "8192",
    "r.Streaming.MaxTempMemoryAllowed": "1024",
    "r.Streaming.LimitPoolSizeToVRAM": "0",
    "r.Streaming.FramesForFullUpdate": "1",
    "r.Streaming.FullyLoadUsedTextures": "1",
    "r.Streaming.Boost": "2",
    "r.ViewDistanceScale": "2",
    "r.StaticMeshLODDistanceScale": "0.5",
    "r.MipMapLODBias": "0",
    "r.MaxAnisotropy": "16",
}


world = unreal.EditorLevelLibrary.get_editor_world()
applied = []
for name, value in CVARS.items():
    command = f"{name} {value}"
    unreal.SystemLibrary.execute_console_command(world, command)
    applied.append(command)

print(json.dumps({"applied": applied}, indent=2))
