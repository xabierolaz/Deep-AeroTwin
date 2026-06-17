import unreal

ar = unreal.AssetRegistryHelpers.get_asset_registry()
assets = ar.get_assets_by_path('/Game/RealSim', recursive=True, include_only_on_disk_assets=False)
print('=== REALSIM ASSETS ===', len(assets))
for a in sorted(assets, key=lambda x: str(x.package_name)):
    try:
        c = str(a.asset_class_path.asset_name)
    except Exception:
        c = str(getattr(a, 'asset_class', ''))
    print(str(a.package_name), '::', c)

paths = [
    '/Game/RealSim/Mass/DA_RealSimCrowdPedestrian',
    '/Game/RealSim/Mass/DA_RealSimRoadVehicle',
]
for p in paths:
    o = unreal.load_asset(p)
    print('\n===== CONFIG', p, '=====')
    if o is None:
        print('  (no cargado)')
        continue
    print('  class:', o.get_class().get_name())
    traits = None
    for prop in ['traits', 'Traits']:
        try:
            traits = o.get_editor_property(prop)
            break
        except Exception:
            traits = None
    if traits is not None:
        print('  traits:', len(traits))
        for t in traits:
            tn = t.get_class().get_name() if t else 'None'
            print('   - TRAIT', tn)
            try:
                print('       ', t.export_text())
            except Exception as e:
                print('        export_text fallo:', e)
    else:
        print('  sin propiedad traits; export del asset:')
        try:
            print(o.export_text())
        except Exception as e:
            print('  export_text fallo:', e)
