import unreal

KW = ['cow','cattle','vaca','bik','bici','cycl','ciclista','person','ped','peaton',
      'human','animal','herd','char','mover','spawn','agent','npc','vehicle','coche',
      'car','bus','mass','crowd','realsim','meta','horse']

print('================ MAPS + KEYWORD ASSETS ================')
ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path('/Game', recursive=True, include_only_on_disk_assets=False)
maps=[]; hits=[]
for a in assets:
    n=str(a.asset_name); pn=str(a.package_name)
    try: c=str(a.asset_class_path.asset_name)
    except Exception: c=str(getattr(a,'asset_class',''))
    if c=='World': maps.append(pn)
    ln=n.lower()
    for k in KW:
        if k in ln:
            hits.append(c+' :: '+pn); break
print('TOTAL_ASSETS', len(assets))
print('MAPS:'); [print('  ',m) for m in sorted(set(maps))]
print('KEYWORD_ASSETS:'); [print('  ',h) for h in sorted(set(hits))]

print('\n================ WORLD ACTORS (no Cesium/Landscape) ================')
try:
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
except Exception as e:
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
SKIP = ('Cesium','Landscape','WorldPartition','SkyLight','DirectionalLight','SkyAtmosphere',
        'ExponentialHeightFog','PlayerStart','WorldDataLayers','Brush','VolumetricCloud')
shown=0
for ac in actors:
    cn = ac.get_class().get_name()
    if any(s in cn for s in SKIP): continue
    try: loc=ac.get_actor_location()
    except Exception: loc=None
    print('  ', ac.get_actor_label(), '::', cn, '::', loc)
    shown+=1
print('NON_ENV_ACTORS', shown)

print('\n================ SPEED CONFIG (RealSim spawner/visualizer/trait) ================')
SPEED_PROPS = ['PedestrianSpeedMetersPerSecond','CarMinSpeedMetersPerSecond',
               'CarMaxSpeedMetersPerSecond','BusSpeedMetersPerSecond',
               'TargetPedestrianCount','TargetCarCount','TargetBusCount']
for ac in actors:
    cn = ac.get_class().get_name()
    if 'RealSim' in cn or 'Crowd' in cn or 'Spawner' in cn or 'Visualizer' in cn:
        print('  ACTOR', ac.get_actor_label(), '::', cn)
        for p in SPEED_PROPS:
            try: print('     ', p, '=', ac.get_editor_property(p))
            except Exception: pass

print('\n================ MASS CONFIG TRAITS ================')
for p in ['/Game/RealSim/Mass/DA_RealSimCrowdPedestrian','/Game/RealSim/Mass/DA_RealSimRoadVehicle']:
    o=unreal.load_asset(p)
    print('  CONFIG', p, '::', None if o is None else o.get_class().get_name())
    if o is None: continue
    tr=None
    for prop in ['traits','Traits']:
        try: tr=o.get_editor_property(prop); break
        except Exception: tr=None
    if tr:
        for t in tr:
            print('     TRAIT', t.get_class().get_name() if t else None)
            try: print('        ', t.export_text())
            except Exception: pass
print('\n================ DONE ================')
