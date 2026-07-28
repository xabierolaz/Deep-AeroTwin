import unreal

subsys = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = subsys.get_editor_world()
print("world:", w.get_name() if w else None)
is_pie = bool(w) and w.world_type == unreal.WorldType.PIE
print("is PIE:", is_pie)

cam_mgr = None
if w:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor.static_class()):
        if 'CesiumCameraManager' in a.get_class().get_name():
            cam_mgr = a
            break
print("cam_mgr:", cam_mgr.get_actor_label() if cam_mgr else None)
if cam_mgr:
    try:
        cams = cam_mgr.get_cameras()
        print("registered cameras:", len(cams))
        for c in cams:
            print("  cam:", c)
    except Exception as e:
        print("err get_cameras:", e)

# sequence state
try:
    players = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.LevelSequenceActor.static_class()) if w else []
    for p in players:
        pl = p.get_sequence_player()
        print("seq actor:", p.get_actor_label(), "playing:", pl.is_playing(), "frame:", pl.get_current_time().time.frame_number.value)
except Exception as e:
    print("seq err:", e)
