# Deep-AeroTwin (PORCE)

Monorepo del proyecto Deep-AeroTwin / PORCE: gemelo digital UAV con Unreal Engine 5.7, pipeline de percepción y control (YOLO + Brain + SITL/ArduPilot) y los papers asociados.

## Demo: vuelo real vs gemelo digital (sincronizado)

Vídeo comparativo del pipeline de telemetría semántica (Pipeline B): a la izquierda el vídeo real de a bordo con las detecciones YOLO de torres; a la derecha el gemelo en Unreal Engine 5 / Cesium, donde el actor proxy aparece en la pose ENU georreferenciada en el momento en que la detección se confirma (t≈1,3 s y t≈16 s) y persiste el resto del vuelo.

▶️ [media/side_by_side_twin.mp4](media/side_by_side_twin.mp4) (24 s, 2560×960)

## Mapa del repositorio

| Directorio | Contenido |
|---|---|
| `Unreal/` | Proyecto Unreal Engine 5.7 (`AirTraffic.uproject`) y plugin `PorceTelemetry`. |
| `papers/` | Los tres papers del proyecto (cada uno es un repo git independiente). |
| `papers/pipeline_b_telemetry/` | Paper principal de telemetría (Pipeline A/B, VRIH). Datos de vuelo real en `data/`. |
| `papers/porce_collision_evasion/` | Paper de planificación de ruta y evasión de obstáculos en tiempo real. |
| `papers/semantic_proxy_3d/` | Paper Semantic Proxy 3D (generación 3D ligera): experimentos, auditorías, generadores y assets. |
| `porce_runtime/` | Sistema operativo: `pipeline/`, `tools/`, `yolo/`, `weights/`, `ardupilot/` (SITL) y lanzadores `LANZAR_*.bat`. Ver `porce_runtime/README.md` y `porce_runtime/docs/WORKFLOWS.md`. |
| `_archive/` | Material histórico fuera del flujo activo. |
| `venv/` | Entorno Python de Windows usado por los lanzadores. |

## Arranque rápido

El sistema se ejecuta desde `porce_runtime/`:

- Arranque completo para paper: `porce_runtime\LANZAR_TODO_PAPER.bat`
- Workflows y detalle operativo: `porce_runtime/docs/WORKFLOWS.md`
- Documentación adicional de Unreal/MCP: `porce_runtime/docs/`

## Sincronización de papers: Local ↔ GitHub ↔ Overleaf

Cada paper tiene **tres copias sincronizadas** que nunca deben editarse por separado:

```
papers/<paper>/…            FUENTE DE VERDAD (aquí se edita siempre)
      │  papers/overleaf_sync/sync.sh  (regenera → compila → pull --rebase → push)
      ▼
papers/overleaf_sync/<paper>/   repo deploy local (main.tex + assets mínimos)
      │ push main                     │ push main
      ▼                               ▼
github.com/xabierolaz/<repo>    git.overleaf.com/<project_id>  → PDF compilado
```

| Paper | Fuente canónica | Deploy | Repo GitHub | Proyecto Overleaf |
|---|---|---|---|---|
| SPPA (JGSA) | `papers/semantic_proxy_3d/semantic_proxy_3d_paper.tex` | `papers/overleaf_sync/sppa/` | `xabierolaz/sppa_yolo3d` | `sppa_overleaf` (id `6a6703fa8532b049b6dfd0fb`) |
| Pipeline B (VRIH) | `papers/pipeline_b_telemetry/pipeline_b_concept.tex` | `papers/overleaf_sync/vrih/` | `xabierolaz/vr_telemetry` | `vr_telemetry` (id `6a670292eb76f187e2892ddf`) |
| PORCE (IEEE TII) | `papers/porce_collision_evasion/…/Main_formato_ieee.tex` | `papers/overleaf_sync/porce/` | `xabierolaz/porce-collision-evasion` | `porce_evasion` (id `6a67039b587b20a0f6b45330`) |

### Uso

- **Editar**: siempre en la fuente canónica (`papers/<paper>/…`). Nunca en `papers/overleaf_sync/` (se regenera entero en cada sync).
- **AUTO-SYNC (recomendado, cero pasos)**: la tarea de Windows **`DeepAeroTwin-AutoSync-Papers`** arranca sola al iniciar sesión y vigila las fuentes canónicas cada 20 s. Al guardar cualquier `.tex/.bib/.cls/.png` de un paper, regenera el deploy, compila y empuja a GitHub + Overleaf automáticamente. Gestión:
  - Estado: `Get-ScheduledTask DeepAeroTwin-AutoSync-Papers` (PowerShell) o el Programador de tareas.
  - Parar: `Stop-ScheduledTask` / deshabilitarla en el Programador de tareas.
  - Manual (si prefieres ver la consola): doble clic en `AUTO_SYNC_PAPERS.bat`.
  - Reinstalarla: `powershell -File papers/overleaf_sync/register_autosync_task.ps1`.
- **Subir a mano (alternativa)**: doble clic en `SYNC_SPPA.bat`, `SYNC_VRIH.bat`, `SYNC_PORCE.bat` o `SYNC_TODOS_LOS_PAPERS.bat`. El script:
  1. Regenera el deploy desde la fuente canónica.
  2. **Compila con latexmk antes de subir** (pdfLaTeX en los tres; si falla, no sube nada).
  3. `git pull --rebase` de GitHub y Overleaf (recoge ediciones hechas en la web de Overleaf).
  4. Commit `update` (autor: Xabier Olaz, sin menciones a herramientas) y push a **ambos** remotos.
- **Reimportar desde cero a Overleaf**: el contenido del deploy (`papers/overleaf_sync/<paper>/`) es exactamente el del proyecto; para re-subirlo como zip, comprime esa carpeta con los archivos en la raíz.

### Reglas

- Overleaf solo admite fast-forward: si un push es rechazado, vuelve a lanzar el `.bat` (el pull --rebase lo resuelve); si hay conflicto real, avisa y se resuelve a mano en el deploy.
- Compilador en Overleaf: **pdfLaTeX por defecto en los tres** (la clase `VRIH2025.cls` lleva guarda `\ifPDFTeX`: con pdfLaTeX no carga fontspec; con XeLaTeX usa Times New Roman real). No hay que tocar Menu → Compiler.
- Commits siempre como `Xabier Olaz <xabierolaz@gmail.com>`, mensaje neutro.
- Editar en la web de Overleaf está permitido (el siguiente sync trae esos cambios a GitHub), pero la edición sustancial se hace en local.

### Cómo se verifica la compilación sin entrar a Overleaf

- **Pre-check local (automático)**: el script compila con latexmk (MiKTeX local) antes de cada push y aborta si hay errores. Overleaf usa TeX Live con los mismos motores (pdfTeX/XeTeX): *compila local ⇒ compila en Overleaf* salvo diferencias raras de versión de paquetes. Es el método oficial de trabajo con Git integration ([docs.overleaf.com](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration)); no existe API oficial de compilación remota en overleaf.com.
- **Verificación remota puntual**: tras cambios grandes se puede abrir el proyecto y comprobar que hay PDF (el enlace "Download PDF" existe y la vista previa renderiza).

### Añadir un nuevo paper al sistema (checklist replicable)

1. **Fuente canónica**: crea `papers/<nuevo>/` con el `.tex`, `.bib`, figuras y tablas. Convención: rutas relativas simples (`figures/…`), nada de paths absolutos.
2. **Compilable en local**: `latexmk -pdf` (o `-xelatex`) debe compilar sin errores en su carpeta. Si la clase exige XeLaTeX solo por fuentes, mete guarda `\ifPDFTeX` como en `VRIH2025.cls` para que pdfLaTeX también funcione — evita depender del compilador de Overleaf.
3. **Deploy**: crea `papers/overleaf_sync/<nuevo>/` con el contenido mínimo para compilar: `main.tex` (renombrado), bib, `.cls`/`.sty`, figuras/tabas referenciadas, y el `.gitignore` de artefactos LaTeX (copia el de `sppa/`).
4. **Repo git local**: `git init -b main` en el deploy; `git config user.name "Xabier Olaz"` y `user.email xabierolaz@gmail.com`; commit `update`.
5. **GitHub**: `gh repo create xabierolaz/<nombre> --private`; `git remote add github …`; push.
6. **Overleaf**: New Project → Upload Project con un zip del deploy (raíz plana, `main.tex` en raíz); comprueba que compila; Menu → Sync → Git → copia la URL `https://git.overleaf.com/<id>`.
7. **Enlazar Overleaf**: `git remote add overleaf <url>`; primera vez: `git fetch overleaf && git merge --allow-unrelated-histories -X ours overleaf/main -m "update" && git push overleaf main` (une historias; después el sync normal basta).
8. **sync.sh**: añade una función `regen_<nuevo>()` (copia fuente→deploy, ver `regen_sppa` como modelo), añade `<nuevo>` al `case` final, y crea `SYNC_<NUEVO>.bat` en la raíz (copia de los existentes).
9. **README**: añade la fila del paper a la tabla de arriba.

### Resolución de problemas

- **Push a Overleaf rechazado**: alguien editó en la web. El `.bat` ya hace pull --rebase; si hay conflicto, resuélvelo en `papers/overleaf_sync/<paper>/` y vuelve a lanzar.
- **"No PDF" en Overleaf pero compila local**: casi siempre es el compilador (fontspec/XeLaTeX) o un archivo referenciado que falta en el deploy; compara con `git status` del deploy.
- **Credenciales**: GitHub va por `gh auth`; Overleaf usa el token git guardado en el Credential Manager de Windows (se genera en Account Settings → Git Integration; username `git`, password = token).
- **Borrar repos GitHub**: requiere `gh auth refresh -h github.com -s delete_repo` o hacerlo en la web (Settings → Danger Zone).
