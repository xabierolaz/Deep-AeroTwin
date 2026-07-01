# PORCE Twin SPPA Backend

`UPorceTelemetryComponent` now supports two interchangeable spawn backends that consume the same `/api/ui/data` obstacle input:

- `UnrealAssets`: current behavior. The component spawns `BikerActorClass`, `CowActorClass`, `TowerActorClass`, or `DefaultObstacleActorClass`.
- `SemanticProxy`: SPPA-style generated 3D proxies using runtime primitive components. The default class is `APorceSemanticProxyActor`, or a custom Blueprint can be assigned to `SemanticProxyActorClass`.

The default backend is `UnrealAssets`, so existing scenes keep their current behavior unless changed.

## Runtime Switch

If `bShowSpawnBackendSwitchUI` is enabled on the `UPorceTelemetryComponent`, Play/PIE shows a viewport button:

```text
PORCE Twin: Unreal Assets
PORCE Twin: SPPA Proxy
```

Clicking it calls `ToggleSpawnBackend()`. Only actors managed by this telemetry component are destroyed and respawned. Existing placed actors, maps, Cesium setup, and configured asset classes are not modified.

If an existing `entity_id` changes canonical class, the asset backend respawns the managed actor with the matching configured class. The SPPA backend keeps the same proxy actor and reconfigures its generated primitive parts.

## Blueprint / Details API

Useful properties and functions:

- `SpawnBackend`: `UnrealAssets` or `SemanticProxy`.
- `SemanticProxyActorClass`: optional custom proxy actor class.
- `bShowSpawnBackendSwitchUI`: enables the viewport button.
- `SetSpawnBackend(NewBackend)`: explicit backend selection.
- `ToggleSpawnBackend()`: switch between both modes.
- `GetSpawnBackend()`: inspect current mode.
- `IsUsingSemanticProxyBackend()`: convenience boolean for UI.

## Environment Override

The backend can be selected before Play with:

```powershell
$env:PORCE_UNREAL_TWIN_SPAWN_BACKEND = "sppa"
```

Accepted SPPA values: `sppa`, `semantic_proxy`, `semantic-proxy`, `proxy`, `generated`.
Any other non-empty value selects `UnrealAssets`.

Optional custom proxy actor class:

```powershell
$env:PORCE_UNREAL_TWIN_SPPA_ACTOR_CLASS = "/Game/Path/BP_MyProxy.BP_MyProxy_C"
```

## Shared Input Contract

Both backends consume the existing obstacle fields already used by the Unreal telemetry consumer:

- Identity: `entity_id`, `object_id`, or numeric `id`.
- Class: `object_type` or `type`.
- Position: `world_m.{north,east,up}`, flat `world_north_m/world_east_m/world_up_m`, or `lat/lon`.
- Confidence: `confidence`.
- Optional heading: `yaw_deg`, `heading_deg`, `azimuth_deg`, `yaw_rad`, or `heading_rad`.

SPPA does not introduce a new endpoint. It is a rendering/backend layer behind the current AeroTwin telemetry path.

## Verification

Run the Unreal reflection/generation smoke after C++ changes to this plugin:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1
```

The check verifies that the `UPorceTelemetryComponent` backend API, default asset-backed mode, `/api/ui/data` endpoint default, the SPPA actor, and the backend enum are exposed to Unreal reflection/Python. It creates a transient telemetry component and checks `SetSpawnBackend()` / `ToggleSpawnBackend()` state transitions. It also spawns `APorceSemanticProxyActor`, calls `ConfigureProxy()` for bike/cow/tower/unknown classes, and checks generated primitive component counts, tags, and collision state.

If Unreal 5.7 is not installed under the usual Epic Games paths, set:

```powershell
$env:PORCE_UNREAL_ENGINE_ROOT = "D:\Path\To\UE_5.7"
```

The full zero-trust audit also runs this smoke by default:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\audit_zero_trust_e2e.ps1
```
