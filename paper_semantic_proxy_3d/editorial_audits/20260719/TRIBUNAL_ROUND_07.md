# TRIBUNAL ROUND 07 — 2026-07-19 (ola de ambición: E7–E12)

**Objeto:** cerrar la trazabilidad de la oleada de experimentos post-hoc exploratorios E7–E12 que eleva la aportación del paquete JGSA-fit (main 23 págs + suplemento 10 págs tras integración). Ciencia sellada intacta por construcción: `reproducibility/sppa_mvfit/` y H1 no tocados; puerta strict verificada en 0 blockers antes de la integración de texto.
**Método:** cada experimento con protocolo congelado por escrito ANTES de computar outcomes (`e10_protocol.md`, `PROTOCOL_E11.md`, MANIFEST de la ola flagship); resultados negativos integrados tal cual (routing refutado, TripoSG-mask como artefacto de paridad documentado).

## Veredicto: la frontera queda medida, no declarada

Tres de las cuatro preguntas que el paper dejaba como prescripción o caveat quedan resueltas con datos; la cuarta (modo oblicuo operativo) está en captura al escribir este acta.

## E7 — Real detector stream (integrado 2026-07-19, recap)

1.902 detecciones (308 tower / 848 cow / 746 biker) de un stream real de 1.394 frames, detector custom real, telemetría MAVLink, GT exacto de 11 torres. Todos los métodos observation-bound (~33 m, y=x); SPPA no gana el IoU 2D de reproyección (0.298 vs 0.42–0.45 cajas); brazo token: refit con token correcto colapsa 0.381→0.025; latencia 11.8 ms. Reportado como caso de estudio honesto en main + S.9.

## E8 — Adversarial family (recap)

Violar el prior estructural preservando la clase recorta la ventaja de +0.209 a +0.141 [0.125,0.157] (ΔΔ −0.068, destruye ~1/3, pierde 8.3%); empates identificables en lattice inclinada 25° y cascade crown. Rompe la crítica de tautología con datos.

## E9 — Part-query (recap)

Tarea operacional de consulta de parte: F1 0.434 (SPPA) vs 0.145 (generic) / 0.111 / 0.087 (hull heuristics); d_c 0.055; conteo exacto 70% vs 0%. Justifica cuantitativamente los roles.

## E10 — Routing de modos MEDIDO (y refutado) + validación de tokens (nuevo)

Protocolo congelado pre-outcome (`benchmarks/real_stream_wave/e10_protocol.md`); outcome: `reproj_iou` per-case sobre las 1.902 detecciones reales.

- **Routing de modos: refutado en este outcome.** Always-SPPA 0.298 [0.290,0.305]; always-OBB 0.446 [0.442,0.450]; oracle inalcanzable 0.452 [0.448,0.456] (SPPA gana solo 17.1% de casos); las mejores políticas por confianza y por mismatch **colapsan a always-proxy** (mejor − always-proxy = 0.0 [0,0]). La prescripción del paper ("route between modes") queda medida y corregida: para el IoU 2D en este stream nadir, el routing no compra nada (oracle +0.006).
- **Validación de tokens: hallazgo positivo medido.** Sobre los 217 casos GT-matched (138 wrong-token / 79 correct): −confianza AUC = 0.847 para detectar token erróneo; el mismatch evidencia-prior separa perfectamente pero INVERTIDO (AUC(−mismatch) = 1.000): los tokens erróneos (vaca/ciclista alucinados sobre torres) reciben alturas monoculares ~1–2 m que encajan sospechosamente bien con su prior erróneo, mientras las torres verdaderas sufren subestimación monocular severa (~5 m vs prior 25 m → mismatch ~1.6). "Ajuste del prior sospechosamente bueno" = firma medida de token erróneo. Alturas nominales por familia congeladas en protocolo: lattice 25.0 m, quadruped 1.5 m, rider 1.8 m.
- Artefactos: `e10_routing.json`, `e10_routing_table.tex`, `fig_e10_routing.png`. Cláusula: la confianza se usa SOLO como señal de routing/validación, nunca como input del fitter (protocolo sellado lo prohíbe como input).

## E12 — Ola neural flagship (caveat retirado con datos)

Mismos 60 casos held-out, mismas 2 condiciones (render oblicuo limpio / máscara top 96×96), mismo protocolo (Enmienda 05), seeds 12345, calibración de frame extendida preservando las entradas 20260717:

| Método | (a) oblique | (b) mask | Notas |
|---|---:|---:|---|
| SPPA-MVFit | 0.561 | — | 9.2 ms CPU, descriptor 1.45 kB |
| TripoSR | 0.128 | 0.231 | 0 crashes |
| Hunyuan3D-2mini-turbo | 0.157 | 0.171 | 2 crashes heredados |
| **Hunyuan3D-2 full (flagship, 50 pasos)** | 0.148 | 0.177 | 0/120 crashes, ~9.3–10.0 s/caso, VRAM 5.965 MB |
| **TripoSG 1.5B RF (50 pasos)** | 0.147 | 0.002* | 0/120 crashes, ~9.1/6.3 s/caso, VRAM 5.811 MB |

\* **Artefacto de paridad documentado, no ocultado:** todos los generadores reciben el PNG as-is (sin RMBG/crop, convención TripoSR/Hunyuan); el pipeline oficial de TripoSG espera RGBA sin fondo. Su 0.002 en mask es artefacto de esa paridad, declarado en el MANIFEST y en el suplemento; excluido de los rangos de titular con nota inline.

**Lectura honesta:** el caveat "mini-turbo ≠ flagship" queda retirado por medición — el flagship full no cierra la brecha (0.148/0.177) y un segundo SOTA local (TripoSG) tampoco (0.147 oblique). La brecha de modalidad se mantiene con 4 generadores medidos. Artefactos: `benchmarks/results/sppa_neural_flagship_wave.{json,md,tex}` + `runs/20260719_flagship_wave/MANIFEST.md`.

## E11 — Modo oblicuo operativo con GT 3D exacto (EN CURSO al escribir este acta)

- **Hecho:** geometría exacta de las 11 torres volcada in-editor (`benchmarks/oblique_twin_wave/gt/tower_geometry.json` + OBJs LOD0 reales): AABB ≈ 8.2 × 7.4 × 20.71 m, pivote en base. Esto sustituye las dimensiones "declaradas" de E7 (base 5×5 m, 25 m nominal) por geometría real → GT 3D para voxel IoU.
- **Bloqueo superado a medias:** el commandlet `-run=pythonscript` no hace tick del motor (Cesium no streamea, meshes sin render-data) — probado en 7 sesiones headless con evidencia (`oblique_twin_wave/logs/`, `CAPTURE_LOG.md`). Reencaminado a la vía probada del repo (editor en vivo vía MCP/remote execution) con autorización del mantenedor.
- **Pendiente:** captura de 308 frames (11 torres × 28 poses: anillos oblicuos 30°/45° + nadir a +60 m), detección YOLO (mismos pesos/conf=0.10 que E7), análisis dual-view con IoU 3D voxel contra la geometría exacta. Protocolo: `oblique_twin_wave/PROTOCOL_E11.md`. **Actualizar esta sección al aterrizar.**

## Estado verificado

- Puerta strict (`reproduce_sppa_mvfit_paper.py --strict`): **0 blockers, H1 pass** (baseline pre-integración, 2026-07-19).
- Ningún número sellado modificado; archivos `sppa_neural_external_wave.*` (ola 20260717) intactos.
- Integración E10+E12 en main/suplemento y recompilación: verificar al cierre (agente en curso).

## Riesgos residuales

1. E10 refuta una prescripción del propio paper: la integración debe leerse como corrección medida (routing → validación de tokens), no como escondida. Es un riesgo editorial controlado y honesto.
2. E11 es evidencia híbrida (telemetría sintética exacta + detector real sobre renders del twin): declarar el aislamiento de variable (geometría de vista) explícitamente para que no se lea como stream real.
3. El artefacto de paridad de TripoSG-mask debe quedar visible en el suplemento; si un revisor lo descubre sin la nota, parecería ocultación.

---

## ADDENDUM 2026-07-20 — REFRAME (pasada 1 de 2): reestructura completa aplicada

**Objeto:** reencuadre del paper a la novedad real según `editorial_audits/20260720/REFRAME_PLAN.md` (consolida las dos auditorías externas 2026-07-19/20). Pasada 1 = reestructura + E10/E12 ya integrados; E11/E14 quedan para la pasada 2 cuando aterricen.

- **Título NUEVO:** "Instant Semantic Proxy Reconstruction for UAV Digital Twins under Degraded Sensing (SPPA-MVFit)".
- **Elevados:** robustez prerregistrada como subsección titular §4.2 (figura standalone + tabla sellada S.9→main; contraste clave: ruido de máscara ~0.001 IoU vs morfología 0.118 ≫ margen, etiquetada "post-hoc analysis of sealed data, conditions preregistered"); latencia 11.8 ms vs 2–15 Hz y link budget 25.8–37.4 kB/s (medido) vs ≥250 kB/s vídeo (modelado) al abstract + filas en tabla runtime; validación de tokens (AUC 0.847 / 1.000) como único relato E10 en main.
- **Podados al suplemento:** figs pipeline-overview, probes-grid, external-gallery, fitting-sequence, runtime-scaling (plegada a filas de la tabla runtime + figura en S.8), paneles (b)(d) de fig_real_stream (split regenerado: `fig_real_stream_main.png` + `fig_real_stream_localization.png`), Alg. 1; tablas mvfit-secondary y surface-metrics; ¶ OBB; detalle descriptor_id/scheduler; probe open-label queda solo en S.3; LLM = una cláusula; custodia seeds/NIST = una frase + puntero.
- **Eliminados de main:** prescripciones de vistas de vuelo (órbitas/pasadas) en §4.6/§4.10/Discussion; narrativa de mode-routing (queda medida solo en S.9 como E10); "in production"; localización E7 → una frase + bloque completo en S.9 (columnas loc/footprint + paneles plan/identity).
- **Líneas rojas respetadas:** LiDAR/noche/niebla/humo = diseño declarado no medido (¶ sensor-agnóstico §3.2: cámara validada); VR = solo motivación (¶ misión §1); "instant" = por objeto (9.4 ms); "compact update descriptor" para 1.45 kB; robustez etiquetada post-hoc de datos sellados.
- **Verificación:** main 24 pp (baseline 24) y suplemento 15 pp (baseline 12) compilan limpios, **0 referencias/citas indefinidas**; puerta strict **0 blockers, H1 pass**; ningún número sellado tocado (`reproducibility/` intacto).
- **Pendiente pasada 2:** figura de misión (3 paneles; otro agente) en el hueco de §1 — NO referenciada aún a propósito; integración E11/E14 al aterrizar.

---

## ADDENDUM 2026-07-20 (tarde) — REFRAME pasada 2 + auditoría de figuras: CIERRE

**Pasada 2 aplicada** (integración de lo que quedó pendiente en la pasada 1):

- **Figura de misión** `fig:mission-twin-delta` en §1: 3 paneles (mundo real con intruso / twin Cesium obsoleto / twin con proxy SPPA), chip con valores sellados (descriptor 1.45 kB, fit 9.4 ms CPU); caption honesto (ilustración conceptual con imaginería existente; números = sealed benchmark values).
- **E11** (`tab:e11`, `fig:e11-oblique`, subsección propia en Results): SPPA gana en oblicuo con CIs separados (0.118 @30° / 0.087 @45° vs 0.037–0.040 mejor baseline); correct-token 0.125/0.147; altura monocular 21.3 m vs GT 20.71 m; nadir = torre invisible al detector (declarado); cross-view: cajas trivialmente autoconsistentes (IoU vs GT 0.02–0.04); consenso SPPA 0.099 [0.095, 0.104]. Etiquetado exploratory post-hoc, posiciones bloqueadas, evidencia híbrida.
- **E14** (`tab:e14`, `fig:e14-lidar`): SIMULATED LiDAR-class returns (raycasts UE 5.7 PIE, sin cámara); envolvente fiel (footprint 7.9×4.0 vs GT 7.42×3.43, yaw ±6°, altura <5%); IoU voxel-exact ~0.08 para TODOS (techo estructural ~1.100/262.144 voxels — SPPA NO supera baselines, reportado); ventaja honesta = economía (2.8k vs 14.3k voxels, precisión 10.5% vs 6.7%); degradación medida: 4/11 torres perdidas a 50% dropout; supervivientes pareados +0.002 [−0.002, +0.006] n=7 (sesgo de supervivencia declarado); limitaciones del sensor simulado declaradas. `fig_e14_fog_pie.png` excluida (ilustrativa floja).
- **Abstract** con cláusula E11/E14 (exploratory/simulated) y límite actualizado: LiDAR/noche/niebla/humo evaluado solo vía corrupciones sintéticas prespecificadas + demo E14 simulada, no en hardware. Declaraciones "LiDAR not measured" de §3.2/Discussion/Conclusion actualizadas coherentemente. Cláusulas de amenazas nuevas (E11/E14 post-hoc, sensor model, techo sub-voxel, survivor bias).
- **Cover letter** con título nuevo + frase E11/E14.

**Auditoría figura a figura del set final** (agente independiente, 15 main + 8 suplemento, visual una a una contra caption/texto): **0 blockers**. 4 defectos menores, **los 4 corregidos y verificados**:

1. `fig:role-colored`: cross-ref §4.5 → `\ref{sec:ablations}` (§4.6).
2. `fig_stream_map`: verificado con datos que t1 SÍ cae en el corredor (154.2 m ≤ 250 m); estaba oculta tras la leyenda → figura regenerada (`tools/jgsa_figures/regen_fig_stream_map.py`, leyenda a lower-left), t1 visible y etiquetada.
3. `fig_e11_oblique` panel (c): sin eje Y/leyenda por solape de layout (span (5,8) tapaba (7,8)); corregido render, añadidos eje Y y leyenda (sppa_mvfit vs aabb). Datos/agregados intactos (md5 idénticos).
4. `fig_runtime_scaling` (supl.): nota de caption declarando las dos corridas (38.7 ms con CSV vs 37.126 ms sin CSV; conclusión >33.3 ms desde 100 objetos inalterada).

**Estado final verificado:** main **28 pp**, suplemento **15 pp**; 0 errores LaTeX, 0 refs/citas indefinidas, 0 overfull nuevos (3 preexistentes en suplemento); puerta strict **0 blockers, H1 pass**; `reproducibility/` y datos sellados intactos; **sin commits** (pendiente confirmación expresa del usuario).

**Veredicto:** apto para envío a JGSA tras las decisiones del usuario (commit, DOI Zenodo/UPNA, checks del día de envío: APC CRUE, JCR Q1 vigente, guía JGSA).

---

## ADDENDUM 2026-07-20 (noche) — SUPLEMENTO ELIMINADO + TRIBUNAL EXTERNO JGSA + PASADA POST-TRIBUNAL

**1. Auditoría de paja (agente independiente):** veredicto — el suplemento NO es load-bearing; nada en él sostiene H1, la robustez o el contrato. **Suplemento eliminado de la submission** (archivo archivado in situ con nota `% ARCHIVED 2026-07-20`); ~35 referencias S.x rewired al reproducibility package; absorciones: Data Availability (+4 líneas: preregistro, enmiendas, NIST seeds, SHA-256, comandos), cláusula auditoría resolver (§3.1), open-label probe (§4.9). Poda main: floats external sanity → prosa con números, `fig:role-colored` fuera, tablas E11/E14 comprimidas, RW comprimido, micro-detalles fuera. Main 28→27 pp.

**2. Tribunal editorial externo (3 agentes agnósticos, lectura íntegra):** veredictos MAJOR (metodología), MAJOR (novelty/JGSA), MINOR (honestidad). Hallazgos clave: (a) §4.2 enumeraba las condiciones de robustez INVERTIDAS vs su tabla (bloqueante); (b) abstract sin etiquetas post-hoc en adversarial/real stream ni scope en AUC; (c) jerga interna ("E7 baselines", "Algorithm 2"); (d) preregistro §6 exige tabla por familia — había quedado solo como barras; (e) pseudo-replicación E11/E14 (CIs sobre detecciones de 11 torres); (f) "does not transfer" demasiado fuerte; (g) encaje geoviz cosmético (decisión: abordar en revisión si se pide).

**3. Re-análisis estadístico (datos existentes, sellos intactos):** cluster bootstrap por torre E11 (CIs más anchos: obl30 0.118 [0.109,0.125], obl45 0.087 [0.061,0.120]; P(Δ≤0)=0; tasas token erróneo 6.0% vs 42.2% declaradas con comentario de dilución); E14 con unidad=torre declarada (CIs apenas cambian); AUC CIs: 0.847 [0.792,0.898], 1.000 [1.000,1.000] (degenerado en frontera, declarado "no population claim"); tabla familia×estrato restaurada (rider_cycle 0.458, mínimo 0.043, CIs de celda post-hoc declarados); Δ pareados sellados vs 6 baselines (vs hull +0.036; inversión de mediana 0.567>0.563 discutida); confirmado bit a bit: unviolated≡CSG-ID, alias curated_family_template≡sppa_text_only.

**4. Pasada post-tribunal aplicada:** 14/14 fixes bloqueantes, 4 tablas restauradas (\input desde benchmarks/), divulgación de proceso (Enmiendas 03/04, Holm p≈0), etiquetas post-hoc homogeneizadas (wrong-family, view-ablation), abstract reescrito ~250 palabras liderado por misión, poda convergente (RW, duplicación fitter, fig 2x2 fuera, micro-timings colapsados, threats en 5 viñetas, conclusión sin repetir números). **Estado final: 27 pp, 0 errores, 0 refs/citas indefinidas, 0 overfull, puerta strict 0 blockers H1 pass.**

**5. Pendiente usuario:** commit de esta pasada (NO commiteado aún); decisión sobre encaje geoviz profundo (uncertainty viz + mapeo 3D Tiles/CityJSON + CRS — medio día, recomendado por editor B pero opcional); checks de envío (APC CRUE, JCR Q1, guía JGSA); DOI (Zenodo/UPNA).
