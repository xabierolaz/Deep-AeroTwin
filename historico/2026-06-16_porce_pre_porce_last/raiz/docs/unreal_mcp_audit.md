# Unreal MCP audit - 2026-05-14

## Project fit

- Project: `Unreal/AirTraffic.uproject`
- Unreal Engine: 5.6
- Existing UE plugins: `PorceTelemetry`, `ModelingToolsEditorMode`, `CesiumForUnreal`, `VaRest`
- Editor status during install: `UnrealEditor.exe` was already running with this project, so the MCP plugin was installed without closing the editor. Full activation requires an editor restart.

## Sources checked

- Epic forum: no official Epic Unreal MCP has been announced yet as of 2026-04-16. Source: https://forums.unrealengine.com/t/is-there-a-plan-to-provide-a-mcp-model-context-protocol-server/2580648/8
- ChiR24/Unreal_mcp: MIT, UE 5.0-5.8, native C++ automation bridge, native HTTP MCP, asset and animation tooling. Source: https://github.com/ChiR24/Unreal_mcp
- db-lyon/ue-mcp: newest and broadest package found (`ue-mcp` 1.0.1, 502+ actions), Windows UE 5.4-5.7, but BUSL-1.1/commercial licensing constraints. Source: https://github.com/db-lyon/ue-mcp
- StraySpark Unreal MCP Server: 359 tools, v3 alpha, UE 5.7 focused and commercial product ecosystem. Source: https://www.strayspark.studio/docs/unreal-mcp-server
- aadeshrao123/Unreal-MCP / `unrealmcp`: 280 commands, Python MCP server or CLI, currently tested primarily on UE 5.7. Source: https://pypi.org/project/unrealmcp/

## Decision

Installed `ChiR24/Unreal_mcp` because it is the strongest fit for this repository today:

- permissive MIT license for project inclusion
- validated compatibility range includes UE 5.6
- native C++ editor bridge
- native Streamable HTTP MCP endpoint, so normal use does not require a Node sidecar
- broad tool coverage for assets, materials, animation blueprints, skeletons, physics, Niagara, Sequencer, levels, actors, logs, tests, and project settings
- larger community signal than the other open options found during the audit

`db-lyon/ue-mcp` is the most aggressive option by action count and recency. I did not install it because its BUSL/commercial license can be a bad surprise for a proprietary, studio, or internal pipeline. It remains the candidate to evaluate if that license is acceptable.

## Installed files

- Plugin source copied to `Unreal/Plugins/McpAutomationBridge`
- `Unreal/AirTraffic.uproject` enables:
  - `McpAutomationBridge`
  - `EditorScriptingUtilities`
  - `Niagara`
- `Unreal/Config/DefaultGame.ini` enables the native MCP endpoint:
  - `bEnableNativeMCP=True`
  - `NativeMCPPort=3000`
  - `ListenHost=127.0.0.1`
  - `ListenPorts=8090,8091`
- `.mcp.json` configures MCP clients to use:
  - `http://localhost:3000/mcp`

## Activation checklist

1. Save work in Unreal.
2. Restart the editor.
3. When Unreal asks to rebuild `McpAutomationBridge`, accept.
4. Confirm the status bar shows `MCP :3000`.
5. Test the endpoint from a terminal:

```powershell
Invoke-WebRequest -Uri http://localhost:3000/mcp -Method Get
```

If Unreal reports missing modules, build `AirTrafficEditor` from Visual Studio against `D:\Epic Games\UE_5.6`.
