# SPPA — Handoff de sesión Kimi Code (2026-07-17)

Documento de continuación para una conversación nueva. Estado real verificado a
fecha 2026-07-17. Léelo entero antes de tocar nada.

---

## 1. Qué es el proyecto

Paper científico **SPPA / SPPA-MVFit**: "Family-Conditioned Multiview Fitting
for Semantic Primitive Proxy Actors in UAV Digital Twins". Claim central (H1,
sellado): un grafo de partes condicionado por familia semántica mejora la
ocupación 3D (voxel IoU) frente a un grafo no semántico de igual presupuesto,
bajo entradas idénticas (siluetas top+side calibradas 96×96).

**Resultado sellado (NO tocar)**: H1 PASS — mean ΔIoU 0.190, CI95 [0.181,
0.199], margen +0.030, n=240 actores, estratos CSG-ID 0.209 / implicit-OOD
0.172. Mediana 9.4 ms (p95 10.6 ms). Preregistro + 5 enmiendas (01–05).

## 2. Dónde vive todo (estructura y junction)

- **Archivos físicos**: `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\` (canónico).
- **Junction NTFS**: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d` →
  apunta al directorio anterior (reparse tag 0xA0000003). Git la atraviesa.
- **Repo git**: `D:\Deep-AeroTwin-UE57-Test` (monorepo de ingeniería Unreal;
  el historial del paper vive aquí como `paper_semantic_proxy_3d/...`).
- **NO hay repo git en AYTE DOCTOR**. Decisión (pendiente post-aceptación):
  mantener la junction hasta el envío; después valorar `git subtree split`.
- Generadores 3D clonados: `D:\Deep-AeroTwin-UE57-Test\third_party\sota_3d_generators\`
  (TripoSR, TRELLIS.2, TripoSG, Direct3D-S2, Hunyuan3D-2, SF3D, SPAR3D, point-e, shap-e)
  con venvs en `_venvs\` (`triposr`, `sf3d`, `sf3d_py310`, `spar3d`, `spar3d_py310`,
  `openai_text3d`; **TRELLIS.2 no tiene venv**, setup.sh es Linux).

## 3. Historial crítico (por qué estamos donde estamos)

El 16-jul el paper tenía un estado validado (tribunal simulado 4 roles:
**CLEAR ACCEPT** a las 22:02, commit `0558971`, 15 págs.) y después, sin
re-auditar, se endureció framing (`b9bfade`) y se **cortó a 10 páginas**
(`f5aec7d`, 23:45) eliminando las secciones SPPA Contract / LM path /
Representation Design Space y 36 referencias. El usuario lo percibió bien:
iba a peor. **JGSA no tiene límite de páginas** (verificado: "no restriction
on the length of the papers") — el corte era innecesario.

**Restauración ejecutada (2026-07-17, sin commit aún)**:
- Paper completo restaurado a `4e2bba7` (34 págs., 9 figuras con capturas de
  detección reales, .bbl 58 refs) — era el estado sellado pre-tribunal.
- Scripts de análisis y resultados restaurados a `0558971` (post-tribunal):
  `analyze_test.py` v2, `confirmatory_summary.json/.md` v2, `integrity_manifest.json`,
  `clean_clone_gate.json`, `check_clean_clone_gate.py`, `verify_package.py`,
  `export_family_table_and_fix_analysis.py`, `render_h1_figure.py`,
  `reproduce_sppa_mvfit_paper.py`, tablas `sppa_mvfit_family_strata.tex` y
  `sppa_mvfit_secondary_deltas.tex`.
- Figuras borradas sin commitear recuperadas desde HEAD.
- Todo staged, **NADA commiteado**. Commit pendiente: PEDIR CONFIRMACIÓN al
  usuario antes de cualquier `git commit`/`push` (regla permanente).

## 4. Hallazgos de la auditoría zero-trust (2026-07-17)

### H1 — Baselines neurales desactualizados pero arsenal disponible
Solo TripoSR + Hunyuan3D-2mini se ejecutaron (cualitativo, 4 casos reales).
Landscape jul-2026: **TRELLIS.2** (Microsoft/Tsinghua, dic-2025, 4B, MIT, ~3 s
@512³, ~12 GB VRAM) es el generador libre de referencia (image y text-to-3D);
**Hunyuan3D 2.5** lidera leaderboards pero es cerrado (2.1 es la open);
**SAM 3D** (Meta, CVPR 2026) descompone escena en objetos individuales con
layout. Excluir pesados del benchmark runtime es defendible; no comparar
calidad offline contra el mejor, no.

### H2 — Números "vs neural" eran tabla hardcodeada
`tools/sppa_sota_benchmark/run_sppa_use_case_sota_benchmark.py:22`:
`NEURAL_REFERENCE` dict hardcodeado (TripoSR 4 casos: 22–36k tris, 0.9–1.35 s;
Shap-E 1 caso) de una auditoría cualitativa previa. Los "48× más ligero" y
"speedups 2500–9000×" se calculan contra esos 5 valores. La Fase B2 los
reemplaza con mediciones reales (Enmienda 05).

### H3 — Caza del elefante: NO hay asesino de novelty; 3 que la dentan
| Trabajo | Qué hace | Por qué no mata la novelty |
|---|---|---|
| PartCrafter (jun-2025, ByteDance/PKU) | Meshes part-estructurados desde 1 imagen | Pesado, offline, sin escala métrica ni update contract |
| SAM 3D (Meta, CVPR 2026) | Imagen → objetos individuales con layout | 32 GB VRAM, offline, sin persistencia de track |
| SuperQuadricOcc (nov-2025) | Ocupación semántica real-time con supercuádricas (driving) | Escena driving; sin partes role-labeled ni telemetría de detector |
Posicionamiento: CityGo (proxy meshes twins urbanos), SpaceControl (control
test-time con primitivas), linaje visual hull/supercuádricas. **Nadie hace**:
telemetría de detector → proxy part-estructurado ligero (~600 tris) en ms CPU
con contrato de actualización persistente.

### H4 — Verificación interna
- **Visual hull SÍ está en el paquete sellado** (`nonsemantic_visual_hull` en
  `run_test_methods.py`): Δ=0.0357, CI [0.027, 0.044] — es el baseline MÁS
  FUERTE. SPPA-MVFit 0.557 vs VH 0.522 IoU medio. Ahora citado (Laurentini).
- **Bug stats confirmado y ya corregido**: `draws_two_sided_p` era inválido
  (≈0.505 siempre: la distribución bootstrap centrada en el observado hace que
  el "p" no baje de 0.5; Holm daba 1.0 a todo). La v2 (`null_centered_two_sided_p`,
  commit `3e7b8f3`) es correcta: todos los p ≈ 0 (<1e-4), Holm significativo.
  La Enmienda 04 D2 ya documentaba este fix prospectivamente.
- **Grid 48/96**: resuelto por Enmienda 04 D1 (resolución ejecutada = 96 para
  ambos brazos; texto del paper consistente: máscaras 96×96, evaluación 64³,
  sensibilidad 48/64/80).
- **OOD honesto**: `_generate_implicit_ood` usa primitivas implícitas
  (superelipsoides, tapered, torus) vs CSG-ID (box/ellipsoid/cylinder) —
  generadores estructuralmente distintos en `source/source_generators.py`.
- **IoU**: `benchmark/metrics.py:evaluate_geometry` con voxelización
  `voxelize_source(actor, 64)` en frame WORLD común. Misma métrica para todos.

## 5. Trabajo hecho en esta sesión (Fase A completa, verificada)

1. Restauración completa (ver §3). 
2. Integrado en el paper: tabla familia×estrato (6 familias × 2 estratos; todas
   las celdas positivas; mínimo compact_vehicle OOD 0.043) + figura H1
   (`figures/sppa_mvfit_h1_occupancy_examples.png`) en Primary Results.
3. 6 citas nuevas en `.bib` (58→64): `laurentini1994visual`, `mo2019partnet`,
   `chen2026sam3d`, `hayes2025superquadricocc`, `liu2025citygo`,
   `fedele2025spacecontrol` + párrafo de diferenciación en Related Work.
4. **Compila limpio**: pdflatex×3 + bibtex → **35 páginas**, 0 errores, 0
   citas/refs indefinidas.
5. Puertas: `reproduce_sppa_mvfit_paper.py --strict` → **0 blockers, H1 pass**.
   `check_clean_clone_gate.py` → pasa todo salvo 3 archivos modificados
   (paper.tex, references.bib, supplement.tex) — se resolverá con el commit.
6. **Enmienda 05 creada**: `SPPA_PROTOCOL_AMENDMENT_05_20260717.md` — registra
   la oleada neural como análisis secundario (subconjunto 60 actores,
   condiciones clean-crop/telemetry-matched, alineación bbox preespecificada,
   métricas IoU/tris/ms/VRAM).

## 6. Pendiente (orden de ejecución)

1. **B2 — Oleada neural medida** (diseño ya fijado en Enmienda 05):
   - Subconjunto: 60 casos sellados (10/familia: 5 CSG-ID + 5 implicit-OOD,
     orden lexicográfico de case_id). Manifest con hashes.
   - Métodos: TripoSR (venv `_venvs/triposr`, probado: 0.46 s warm); Hunyuan3D-2mini
     si se encuentra su env de las corridas 20260703 en
     `experiments/sppa_sota_benchmark/runs/`; SF3D documentado como timeout;
     SPAR3D weights gated; TRELLIS.2 intentar solo si trivial (sin venv).
   - Inputs: (a) render sombreado oblicuo del actor (generoso); (b) máscara top
     96×96 real (harsh). Filas SPPA: lectura de `raw_metrics.csv` (clean).
   - Alineación: escala uniforme a bbox GT + centro bbox GT, yaw=frame GT; sin
     ajuste manual; crashes reportados, no excluidos salvo fallo duro.
   - Métricas: voxel IoU 64³ (`metrics.py:evaluate_geometry`), tris, ms warm,
     VRAM pico. Salidas: `benchmarks/results/sppa_neural_external_wave.{json,md,tex}`.
   - NO tocar: sealed_predictions*, raw_metrics.csv, confirmatory_summary.json,
     integrity_manifest.json.
2. **B3 — Tabla Pareto** IoU vs (tris, ms, VRAM) en el paper con los métodos
   externos medidos; reemplazar/declarar `NEURAL_REFERENCE`.
3. **D1-D2**: actualizar `SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md` (mover filas
   de PROHIBIDO a REPORTADO según B2); repoisicionar novelty si hace falta;
   **commit** (pedir confirmación); re-pasar puertas; tribunal simulado sobre
   la versión FINAL (lección del 16-jul: nada de cambios post-ACCEPT).
4. **Envío JGSA**: verificar APC UPNA (`biblioteca.revistas@unavarra.es`) y JCR
   Q1 vigente el día del envío. Package: main PDF + suplemento corto +
   highlights + cover letter + `reproducibility/sppa_mvfit/`. NO adjuntar el
   suplemento técnico de 38 págs.

## 7. Comandos clave

```powershell
# Puertas (desde raíz del repo D:\Deep-AeroTwin-UE57-Test)
python paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/check_clean_clone_gate.py
# Compilar paper (en D:\AYTE DOCTOR\SPPA_semantic_proxy_3d)
pdflatex -interaction=nonstopmode semantic_proxy_3d_paper.tex; bibtex semantic_proxy_3d_paper; pdflatex ... (x2)
```

## 8. Gotchas del entorno

- Windows + Git Bash. Python 3.12 sistema. GPU RTX 5090 32 GB.
- **Encoding**: prints con caracteres Unicode (Δ etc.) rompen con cp1252 →
  usar `PYTHONUTF8=1` o ASCII en scripts Python por consola.
- MiKTeX instalado (`pdflatex`, `bibtex` en PATH).
- Aprobaciones: el modo yolo se activa con `/yolo` o arrancando
  `kimi resume --yolo`; si aparecen prompts, el usuario decide uno a uno.
- `git status` del monorepo muestra muchos cambios ajenos (Unreal, pipeline) —
  no tocar; trabajar solo bajo `paper_semantic_proxy_3d/`.

## 9. Commits de referencia

| Hash | Qué es |
|---|---|
| `9f5c43f5` | Oleada neural medida (B2) + tabla Pareto (B3) + matriz (D1) + poda de figuras 36→33 págs. + S1/S2 en suplemento |
| `4e2bba7` | Paper completo 34 págs. sellado (estado restaurado del paper) |
| `0558971` | CLEAR ACCEPT tribunal + análisis v2 (estado restaurado de scripts/resultados) |
| `3e7b8f3` | Fix stats v2 (null-centered p) |
| `a0f5887` | Seal inicial (21:25) |
| `f5aec7d` | Corte a 10 págs. (superseded en working tree) |

---

## 10. Sesión 2026-07-17 (tarde): B2 COMPLETA + B3 + D1

**B2 oleada neural medida — HECHA** (Enmienda 05, sin tocar sellado):
- Toolchain nuevo: `tools/neural_external_wave/` (wave_common, step1 subset,
  step2 inputs, run_triposr_wave, run_hunyuan_wave, step4 evaluate).
- Artefactos: `benchmarks/neural_external_wave/` (subset_manifest 60 casos,
  inputs 120 PNG + hashes, gt_bboxes, runs/20260717_wave con logs+mallas,
  wave_calibration.json, wave_rows/). Salidas: `benchmarks/results/
  sppa_neural_external_wave.{json,md,tex}`.
- Resultado: SPPA-MVFit 0.561 IoU / 536 tris / 9.2 ms CPU / 1.45 kB;
  TripoSR 0.128(a)/0.231(b) 28k-46k tris ~0.38 s 1.9 GB; Hunyuan3D-2mini-turbo
  0.157(a)/0.171(b) 0.69M-3.1M tris 1.35-1.92 s 4.6-4.7 GB. 2 crashes duros
  (Hunyuan oblique, quadruped x2) reportados. SF3D/SPAR3D/TRELLIS.2 excluidos
  con motivo documentado. Hallazgo extra: las máscaras top dan MEJOR IoU que
  el render limpio en ambos generadores (alucinación de estructura ocluida).
- Voxelizador de mallas propio (z-slice even-odd, tolerancias en frontera) con
  self-test (caja alineada 0.990, desplazada 1.000). Alineación: convención de
  frame fija (48 candidatas, 12 casos calibración, 2 pasadas 32/64), escala
  uniforme a bbox GT + centro GT. Voxelizer mesh GLB/OBJ vía trimesh.
- **B3**: nueva subsección "Measured External Neural Wave on Sealed Held-Out
  Cases" en Secondary Systems Evidence con tabla Pareto (incluye
  descriptor_bytes y visual hull de contexto). **D1**: matriz de evidencia
  actualizada (fila oleada PASS, Amendment 01-05) + párrafo future work en
  Discussion (CMA-ES/differentiable, supercuádricas, amortizado).
- Compila limpio: 36 págs., 0 errores, tabla sin overfull. Puertas:
  reproduce --strict 0 blockers H1 pass; clean-clone falla SOLO por los 4
  archivos modificados de siempre + matriz (se resuelve con el commit).
- MiKTeX bueno = `C:\Program Files\MiKTeX\miktex\bin\x64` (pdflatex.exe). El de
  usuario (`AppData\Local\Programs\MiKTeX`) está ROTO (DLLs faltan, 0xC0000135).

**Pendiente sin cambios**: commit (PEDIR CONFIRMACIÓN), tribunal simulado sobre
la versión FINAL, envío JGSA (APC UPNA + JCR Q1 el día del envío).

## 11. Sesión 2026-07-17 (noche): auditoría de extensión + poda quirúrgica de figuras

**Auditoría (verificado en Springer JGSA submission guidelines, journal 41651)**:
JGSA NO tiene límite de páginas ("no restriction on the length of the papers").
Recortar por recortar no suma; la poda se hizo solo donde había duplicidad real.

**Poda ejecutada** (main 36→33 págs., 10→6 figuras; suplemento 2→4 págs.):
- Eliminada fig. evidence-channel-coverage (triple redundante: prosa + tabla
  `sppa_evidence_channel_coverage.tex` + figura decían lo mismo, 1/2/4-5 canales).
- Eliminada fig. silhouette-replay grid (contenida íntegramente en la zoom audit).
- Zoom-detection audit → Supplementary Figure S1 (caption ampliado absorbiendo
  la evidencia full-frame de la silhouette-replay).
- Visual-part-evidence grid → Supplementary Figure S2.
- Tabla `sppa_observation_fusion_audit.tex`: nueva columna Conf. con la
  confianza YOLOE desde la fuente de verdad
  (`real_image_assumed_flight_replay.json` → `rows[].detector_confidence`:
  biker 0.40, tower 0.46, tractor 0.52, tractor_trailer 0.47).
- Suplemento: añadido `\usepackage{graphicx}`, numeración `S\arabic{figure}`,
  sección "Supplementary figures" con S1+S2 (captions originales preservados).
- Main: 3 punteros de texto a "Supplementary Figure~S1/S2" (el main no usa \ref
  al suplemento; son PDFs separados).
- Overfull introducido por la nueva columna resuelto: columnas L ajustadas +
  `tractor\_\allowbreak{}trailer`. Quedan 2 overfull PREEXISTENTES ajenos a esta
  poda (párrafos líneas 97-105 y 628-643 del main; ya estaban).

**Verificación**: main y suplemento compilan 0 errores / 0 refs indefinidas;
inspección visual de páginas afectadas (PyMuPDF del Python 3.12 sistema —
el Python gestionado NO tiene renderer de PDF); puerta
`reproduce_sppa_mvfit_paper.py --strict` → 0 blockers, H1 pass.
**GOTCHA puerta**: hay que ejecutarla desde la RAÍZ DEL WORKSPACE
(`D:\Deep-AeroTwin-UE57-Test`) vía junction; desde el directorio canónico falla
en los contract tests (`_discover_repo_root` busca `.git` hacia arriba y no lo
encuentra en `D:\AYTE DOCTOR\...`). No es un fallo del paper.

**Nota editorial pendiente**: `JOURNAL_DECISION_20260716.md` línea ~30 aún dice
"target ~10-12 pages" (decisión revertida); corregir cuando el usuario lo apruebe.

**Commit HECHO**: `9f5c43f5` (327 ficheros; `supporting_artifacts/` 22 GB y
`neural_external_wave/runs/` 3.4 GB excluidos vía `.gitignore` del paper —
regenerables). Clean-clone gate PASS (0 missing/untracked/modified) y strict
0 blockers sobre el estado commiteado. NOTA: esta línea y la fila de §9 quedan
sin commitear (doc de trabajo; irán con el próximo commit).

**Tribunal R3 HECHO** (2026-07-17, `editorial_audits/20260717/TRIBUNAL_ROUND_03.md`):
**MINOR_REVISION** (Editor MINOR, Stats MINOR, Repro ACCEPT, Lit MINOR).
8 P0 consolidados, TODOS editoriales/textuales (ciencia sellada intacta):
(1) cover letter/JOURNAL_DECISION describen el manuscrito cortado obsoleto +
título inconsistente; (2) highlights con números obsoletos (~685 tris/0.22 ms);
(3) prosa run-ID Unreal líneas 1401-1471 duplica tabla (comprimir); (4)
framing JGSA/geovisualization ausente del manuscrito (intro+keywords); (5)
"twelve disjoint calibration cases" es FALSO (12/12 solapan con los 60
evaluados; corregir + discloser dirección conservadora); (6) CI secundario en
texto [0.117,0.143] vs sellado [0.116,0.144]; (7) motivo exclusión SF3D
contradictorio entre secciones; (8) dos frases sobre competidores sin cita
(claves bib ya existen). Corrección de registro: bib real = 64 refs (no 147),
64/64 citadas, cero huérfanas.

**Pase de respuesta HECHO + Tribunal R4 = CLEAR ACCEPT** (2026-07-18,
`editorial_audits/20260718/TRIBUNAL_ROUND_04.md`, 4/4 ACCEPT, cero P0 nuevo):
- Los 8 P0 de R3 corregidos (cover letter + título unificado + scorecard fuera;
  highlights 536 tris/9.2 ms; JOURNAL_DECISION "full restored version, 34 pp";
  prosa run-ID comprimida 40→21 líneas; párrafo framing JGSA en intro + keyword
  "geovisualization of dynamic objects" + batty2018digitaltwins + ogc2023tiles;
  "disjoint"→solape 12/12 declarado con dirección conservadora en tex+md; CI
  [0.116,0.144]; SF3D harmonizado py3.12/py3.10; citas SF3D/SPAR3D/TRELLIS.2
  colgadas; + P1s: caption n=58 + "unrounded per-case values", timing
  "single-call descriptive", intervalos "per-comparison and unadjusted",
  payload ≈3.2×10⁴×, frase asimetría de input, typo Holm-style, epic2026nanite,
  notas SF3D/SPAR3D copiadas a benchmarks/neural_external_wave/exclusion_notes/
  + pointers de step4, .gitignore aclarado, compresión narrativa stress-test
  con back-ref a la oleada, wording repo-root en suplemento).
- Main 34 págs., bib 65 entradas (65/65 citadas, 0 huérfanas), 0 errores /
  0 refs indefinidas; strict 0 blockers.
- Clean-clone falla SOLO por los 3 ficheros corregidos sin commitear
  (paper.tex, references.bib, submission_supplement.tex) → pasa con el commit.
- **OJO commit**: incluir `benchmarks/neural_external_wave/exclusion_notes/`
  (untracked; `git commit -a` NO lo recoge) + actas R3/R4 + handoff.
- Lección R4: el suplemento declara "p-values del artefacto no se usan en el
  manuscrito" → la opción consistente fue etiquetar intervalos secundarios como
  no ajustados, NO añadir p-Holm al texto.

**Pendiente**: commit de la versión CLEAR ACCEPT (PEDIR CONFIRMACIÓN) →
re-pasar clean-clone → envío JGSA (APC UPNA biblioteca.revistas@unavarra.es +
JCR Q1 el día del envío; package: main PDF 34 pp + suplemento 4 pp S1/S2 +
highlights + cover letter + `reproducibility/sppa_mvfit/`).

---

## 2026-07-18 — FEEDBACK EXTERNO UNIFICADO + REESTRUCTURACIÓN MAYOR (R5)

**Origen**: 4 revisiones externas independientes (F1 revisor doble ciego, F2
auditoría Q1/tribunal, F3 revisor Q1, F4 probabilidades por venue). Contrastados
TODOS los puntos con 4 agentes (numérico/cobertura/viabilidad/estructura) sin
fiarse de ninguno → `editorial_audits/20260718/UNIFIED_EXTERNAL_FEEDBACK.md`
(14 temas; errores de los revisores documentados: F2 "14 págs", F1 "40×",
corrupciones "inexistentes" que sí existían selladas). Decisiones usuario
D1–D4 = "lo más ambicioso y honesto": test externo SÍ, role-IoU SÍ con mapeo
congelado ex-ante, título se mantiene, poda agresiva.

**Fase A — 12 piezas de evidencia nueva** (todo post-hoc FUERA del sello salvo
la tabla de corrupciones, que es prerregistrada y sellada):
`benchmarks/mvfit_posthoc_analysis/` (T1 robustez 5 condiciones Δ0.118–0.190;
T2 2×2 grafo×fitting Generic-nofit 0.180; T3 Chamfer 0.008 + F-score 0.831;
T4 fallos lattice 5/240 sub-voxel + convergencia; T5 drop-one-family
0.152–0.214) y `benchmarks/mvfit_reviewer_experiments/` (E1 familia errónea
0.205 vs generic 0.367 — prior malo PEOR que ninguno; E2 top-only 0.458 /
side-only 0.545; E3 OBB 0.252 ≈ AABB; E4 barrido 11/21/31/61 = rodilla;
E5 3 grafos genéricos alternativos TODOS peores → ventaja conservadora;
E6 role-aware IoU 0.319 vs shuffle 0.053, mapeo congelado ex-ante).
**Test externo** `benchmarks/external_mesh_sanity/`: 52 mallas reales
(Objaverse LVIS + ModelNet40): SPPA 0.413 vs generic 0.370 (Δ+0.043 n.s. —
el margen NO se replica) y visual hull 0.656 domina; reportado con honestidad
total (modos de fallo: mismatch plantilla, geometría abierta, jirafa=horse).

**Fase B+C — paper reestructurado**: main 34→**24 págs** (nuevas §7 Robustness
and Boundary Conditions y §8 External Sanity Check; §10.x al suplemento, que
pasa a 21 págs; 22→18 tablas main con las 6 nuevas; disclaimers 1/sección +
puntero §13; §3 LLM → 1 párrafo; frase de victoria neural ELIMINADA → framing
input-modality mismatch; tabla ontología 15/23/34/64/95/6; SMPL/3DMM/Hydra +
4 refs bib nuevas; construcción grafo genérico + autoría documentada; margen
+0.030 con potencia 90% citada; hardware spec; números resolución; checkpoint
yoloe-26s-seg.pt; abstract con frase honesta de no-réplica externa).
Logs: `PRUNE_LOG.md`, `INTEGRATION_LOG.md` (misma carpeta). Backup pre-poda:
`D:\Deep-AeroTwin-UE57-Test\sppa_audit\backup_pre_prune\`. Copia de trabajo de
integración (ya sincronizada al canónico): `...\sppa_integration_work\`.

**Tribunal R5 = ACCEPT con MINOR ISSUES 4/4** (`TRIBUNAL_ROUND_05.md`):
20/24 verificaciones OK; 8 hallazgos menores H1–H8 TODOS corregidos el mismo
día (OBB "practically identical", +0.002 redondeo, rango 0.09–0.37, "seven
actor methods", nota timings re-run, boundary externa en suplemento, ref S.1,
frase primitivas triviales §8).

**Estado actual**: main 24 págs + suplemento 21 págs, 0 errores / 0 refs
indefinidas (compilar con `-jobname=sppa_check` / `supp_check` — Acrobat tiene
bloqueado `semantic_proxy_3d_paper.pdf`; al cerrarlo, recompilar jobname
normal). Strict 0 blockers. Clean-clone falla SOLO por los 3 ficheros editados
sin commitear → pasa con el commit.

**Pendiente AHORA**: commit de TODO (PEDIR CONFIRMACIÓN): 3 ficheros paper +
`benchmarks/mvfit_posthoc_analysis/` + `benchmarks/mvfit_reviewer_experiments/`
+ `benchmarks/external_mesh_sanity/` (OJO: puede pesar — revisar con git
status/du; las mallas descargadas quizá deban ir a .gitignore conservando
scripts+JSON+tablas) + `benchmarks/neural_external_wave/exclusion_notes/`
(sigue untracked) + actas 20260718/ + figura external_sanity_qualitative.png
+ handoff. Después: re-pasar clean-clone y actualizar JOURNAL_DECISION /
HIGHLIGHTS / cover letter si mencionan "34 pp" o tablas obsoletas.

---

## 2026-07-18 (tarde) — TRANSFORMACIÓN JGSA-FIT + TRIBUNAL R6 (ESTADO VIGENTE)

**Esta sección sustituye al "Estado actual" anterior.** El paquete se
reestructuró para JGSA (`Journal of Geovisualization and Spatial Analysis`,
Springer, Q1, decisión en `JOURNAL_DECISION_20260716.md`):

- **Main** `semantic_proxy_3d_paper.pdf`: **20 págs, 6 secciones + Data/Code
  Availability, 6 tablas, 14 figuras** (3 renders Blender + 9 charts + 2 reuso
  legítimo; scripts `tools/jgsa_figures/` + MANIFEST.md). 0 errores, 0 refs
  indefinidas, 3 overfull ≤12.9 pt.
- **Suplemento** `semantic_proxy_3d_submission_supplement.pdf`: **9 págs,
  secciones S.1–S.9** (con punto; el main apunta 7 veces a "Section S.9" =
  "Sealed and Post-Hoc Analysis Tables", que contiene TODAS las tablas
  selladas y post-hoc incluidas las nuevas OBB y role-aware). 0 errores.
- Actas del proceso: `editorial_audits/20260718/` — UNIFIED_EXTERNAL_FEEDBACK,
  PRUNE_LOG, INTEGRATION_LOG, TRIBUNAL_ROUND_05, JGSA_BOARD_AUDIT,
  JGSA_TRANSFORM_LOG, TRIBUNAL_ROUND_06.
- Auditoría zero-trust JGSA (3 agentes externos): `sppa_audit/`,
  `audit_sppa/AUDITORIA_SPPA.md`, `jgsa_bibliometric_profile.md` (en
  `D:\Deep-AeroTwin-UE57-Test`).

**Tribunal R6 = MAJOR de empaquetado, ciencia intacta**
(`TRIBUNAL_ROUND_06.md`): todos los hallazgos eran figuras/punteros/captions
y están TODOS corregidos (captions family-graphs/role-colored/wrong-family,
tablas OBB+role-aware añadidas a S.9, figura role-colored sin etiqueta "E6:",
figura external-scatter reescrita como scatter real por caso — medias
verificadas 0.413/0.370/Δ+0.043 —, tabla externa sin overfull de 33 mm,
numeración S.x con punto, `\externaldocument` al nombre canónico, docs de
envío actualizados a 20 págs). Compilación final con NOMBRES CANÓNICOS (sin
-jobname): main 20 págs + suplemento 9 págs, 0 undefined. Strict: 0 blockers,
H1 pass.

**Pendiente AHORA (en orden)**:
1. **Commit de TODO (PENDIENTE CONFIRMACIÓN DEL USUARIO — NO commitear sin
   ella)**: 3 ficheros paper (.tex main/supp + referencias si cambió),
   `benchmarks/mvfit_posthoc_analysis/`, `benchmarks/reviewer_experiments/`,
   `benchmarks/external_mesh_sanity/` (meshes/cache/cases YA en .gitignore —
   750 MB fuera; entran scripts+JSON+tablas), `benchmarks/neural_external_wave/
   exclusion_notes/`, `figures/fig_*.png`, `tools/jgsa_figures/`, actas
   20260718/, kimi_code.md, .gitignore, COVER_LETTER_DRAFT.md,
   JOURNAL_DECISION_20260716.md. Tras commit: re-pasar clean-clone gate.
2. **R6-H7 / ancla externa**: Data/Code Availability dice "upon publication"
   sin repo público ni DOI → decidir Zenodo o repo institucional ANTES de
   enviar (riesgo editorial real).
3. Checks del día de envío (en JOURNAL_DECISION): APC Springer/CRUE con
   biblioteca UPNA, JCR Q1 vigente, guía de autor JGSA (anonimato si aplica).
4. Opcional: `miktex update` (aviso out-of-sync inofensivo).

**Números sagrados**: sin cambios (ver sección anterior). La ciencia sellada
no se ha tocado en R6; las figuras nuevas se derivan de artefactos sellados o
post-hoc ya commiteados/en disco.

---

## 2026-07-19 — E7/E8/E9 INTEGRADOS + HANDOFF A CLAUDE CODE (ESTADO VIGENTE)

**Esta sección sustituye al estado anterior.** Petición del usuario: "arregla
todo lo que tenemos en contra". Se atacaron los 4 puntos débiles con
experimentos NUEVOS (agentes Debussy y Ethan), no solo redacción:

- **E7 real stream** (`benchmarks/real_stream_wave/`): 1902 detecciones reales
  (1394 frames, detector custom, mavlink, GT exacto 11 torres). Bug de doble
  escalado encontrado y corregido por el agente. Resultados honestos: todos
  observation-bound ~33 m; SPPA NO gana IoU 2D (0.298 vs 0.42-0.45); brazo
  token: 0.381→0.025 al forzar token correcto; latencia 11.8 ms.
- **E8 adversarial** (`benchmarks/mvfit_reviewer_experiments/e8_adversarial_family/`):
  120 actores que violan priors de familia → ventaja cae +0.209→+0.141
  [0.125,0.157] (destruye 1/3); empates en leaning lattice y cascade crown;
  SPPA pierde 8.3% actores. Rompe la tautología con datos.
- **E9 part-query** (`...\e9_role_query/`): F1 0.434 vs 0.145/0.111/0.087;
  d_c 0.055; conteo 70% vs 0%. Frontera honesta: hull gana en copas
  fusionadas; rider/fork=0.
- **Paper**: main 23 págs (15 figs, 7 tabs), suplemento 10 págs (S.1–S.9 con
  3 tablas nuevas). Intro con contribuciones (i)(ii)(iii); threats declara la
  tautología; abstract/conclusión incluyen adversarial+stream. 0 undefined.
- OJO heredoc bash: mangla `\` en tablas .tex → usar siempre Write tool
  (lección aprendida con real_stream_main_table.tex / token_arm).
- **Handoff a Claude Code**: `CLAUDE_CODE_HANDOFF.md` (este directorio).
  Claude Code configurado autónomo: `~/.claude/settings.json` →
  permissions.defaultMode=bypassPermissions (token z.ai dentro, NO copiar).

**Pendiente AHORA**: (1) strict gate, (2) acta
`editorial_audits/20260719/TRIBUNAL_ROUND_07.md`, (3) COMMIT — sigue SIN
confirmación del usuario, (4) decisión DOI/Zenodo, (5) checks día de envío.
