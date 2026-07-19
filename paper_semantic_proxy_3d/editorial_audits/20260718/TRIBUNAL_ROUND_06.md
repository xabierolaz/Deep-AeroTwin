# TRIBUNAL ROUND 06 — 2026-07-18 (post-transformación JGSA-fit)

**Objeto:** versión JGSA-fit del paquete — main reestructurado a 6 secciones + Data/Code Availability (20 págs con bibliografía, 14 figuras, 6 tablas) y suplemento formal (9 págs, secciones S.1–S.9). Las 14 figuras son artefactos reales generados desde datos/Blender (`tools/jgsa_figures/`, MANIFEST incluido).
**Método:** tribunal externo (agente-23) con lectura completa del PDF y verificación de claims contra artefactos; la ciencia sellada (H1, estratos, márgenes) quedó intacta por construcción — R6 auditaba empaquetado, figuras y punteros.

## Veredicto: MAJOR REVISION *de empaquetado* (ciencia intacta)

Todos los hallazgos eran de presentación/figuras/punteros, ninguno tocaba un número sellado. Resueltos en dos tandas (mismo día).

## Hallazgos y resolución (TODOS aplicados 2026-07-18)

### Tanda 1 (pre-compactación, verificada)

- **Caption `fig:family-graphs`** describía un panel "generic" fantasma que no existe en la figura → reescrito contra la figura real. ✅
- **Caption `fig:role-colored`** no describía los paneles (a) render Blender + (b) chart → ahora describe ambos con los números 0.319 / 0.053 / 0.017 y remite a Section 4.5. ✅
- **Caption `fig:wrong-family`** matizaba mal los off-diagonal → reescrito: "fall well below the diagonal" con las excepciones reales (compact/articulated y lattice). ✅
- **Chain-of-custody** de Methods: párrafo comprimido (tonelaje de log → proporción de paper). ✅
- **Chamfer** sin ancla: ahora cita Supplementary Section S.9. ✅
- **Timings 9.4 vs 12.6 ms**: nota explícita en el párrafo de budget (re-run post-hoc, IoU bit-exact con el sellado). ✅
- **Caption Tabla 5**: typo de signo (SPPA−Generic). ✅

### Tanda 2 (esta sesión)

- **R6: tablas OBB y role-aware citadas pero no incluidas** → creadas en S.9 del suplemento (`tab:supp-obb-baseline` desde `benchmarks/mvfit_reviewer_experiments/e3_obb/obb_baseline_table.tex`; `tab:supp-role-aware` desde `.../e6_role_aware/role_aware_iou_table.tex`), con punteros desde el main ("table in Supplementary Section S.9" en párrafos OBB y Role-aware; `Figure~\ref{fig:role-colored}b` junto a 0.319). ✅
- **`fig_role_colored_blender.png`**: el panel (b) llevaba etiqueta interna de laboratorio "E6:" → regenerado sin ella ("(b) Role-aware IoU vs shuffle controls"; `tools/jgsa_figures/compose_role_colored.py`). ✅
- **`fig_external_scatter.png`** era un bar chart por familia mientras el caption prometía scatter por caso → reescrito `tools/jgsa_figures/fig_external_scatter.py`: scatter real x=Generic / y=SPPA, 52 puntos coloreados por familia, diagonal y=x. Medias verificadas desde `results.jsonl` (520 filas): SPPA 0.413, Generic 0.370, Δ pareado +0.043 — coincide con caption y tabla. ✅
- **Tabla externa (main) desbordaba 94.8 pt (~33 mm) al margen** → cabeceras de familia abreviadas + pie reestructurado en líneas cortas; generador `benchmarks/external_mesh_sanity/scripts/analyze.py` actualizado para que el fix persista; caption declara la abreviatura. ✅
- **Overfull 27 pt** en párrafo de citas largas → `\sloppy` local. ✅
- **Suplemento numeraba secciones "S1…S9"** mientras el main apunta 7 veces a "Section S.9" → `\thesection` ahora `S.\arabic{section}`; verificado en PDF: S.1–S.9 con punto, y "Sealed and Post-Hoc Analysis Tables" es efectivamente S.9. ✅
- **`\externaldocument`** del suplemento apuntaba al jobname de chequeo (`sppa_check`) → ahora `semantic_proxy_3d_paper` (nombre canónico de envío). ✅
- **Docs de envío stale** (24 págs/3 figs/18 tabs/21-pág suplemento) → cover letter y journal decision actualizados: 20 págs, 14 figuras, 6 tablas, suplemento 9 págs. ✅

## Estado verificado tras los fixes

- `semantic_proxy_3d_paper.pdf`: **20 págs**, 0 referencias/citas indefinidas, 3 overfull residuales ≤12.9 pt (<5 mm, tolerables).
- `semantic_proxy_3d_submission_supplement.pdf`: **9 págs**, 0 indefinidas, overfull ≤10.8 pt; secciones S.1–S.9; tablas OBB y role-aware presentes con valores 0.252/0.248 y 0.319/0.053/0.017.
- QA visual de las 2 figuras regeneradas: sin "E6:", scatter correcto con diagonal y anotación CI.
- Puerta strict (`reproduce_sppa_mvfit_paper.py --strict`): 0 blockers, H1 pass (sin cambios — ciencia intacta).

## Riesgos residuales (decisión del usuario ya tomada: se mantienen)

1. **Cultura JGSA de validación en casos reales**: nuestro test externo (n=52) dice honestamente que el margen +0.030 NO transfiere fuera de la distribución de diseño (Δ +0.043, CI [−0.007, +0.094]). Se queda con framing honesto; es un riesgo editorial conocido y asumido.
2. **R6-H7 — Availability sin ancla externa**: Data/Code Availability dice "upon publication" pero no hay repo público ni DOI. Acción pre-envío recomendada: archivo Zenodo o repo institucional con DOI.
3. Compilación MiKTeX local muestra aviso "User/administrator updates are out-of-sync" (inofensivo, pero conviene `miktex update` antes del envío).

## Apéndice R6.2 — Auditoría figura a figura (2026-07-18 noche, petición del usuario)

Revisión visual de las 14 figuras contra sus captions + grep de texto rojo/TODO/placeholders (0 hits en los .tex). Resultado: **6 defectos encontrados y corregidos el mismo día**:

1. **`fig_probes_grid.png` — pie de figura CORTADO a mitad de palabra** ("...competing SPPA column. Sha"). La imagen fuente (2858 px) maquetaba el pie para su ancho completo; el recorte a 1520 px lo truncaba. Fix: `fig_probes_grid.py` recorta también a 986 px de alto (pie eliminado; la caption del paper ya cubre esa información). Verificado que la fila tractor+trailer queda íntegra. ✅
2. **Caption de `fig:probes-grid` describía 3 columnas que NO son las de la figura** ("constraint-fused footprint proposal" no existe; omite Shap-E/Point-E/TripoSR/Hunyuan3D). Reescrita contra las 7 columnas reales con nota de input-modality mismatch. ✅
3. **Caption de `fig:fitting-sequence` prometía "intermediate coordinate-descent sweeps"** que la figura no muestra. Reescrito como (a) siluetas (b) init (c) convergido (d) GT. ✅
4. **Caption de `fig:pareto-neural` decía eje x "wall time"**; la figura muestra **payload en bytes**. Corregido + refuerzo "not a leaderboard". ✅
5. **Caption de `fig:runtime-scaling` hablaba de "actor-proxy and HISM backends"** (la figura solo muestra HISM) y afirmaba que los updates parciales aguantan a 500 objetos — dato que está en la TABLA (29.787 ms, schedule 10% changed-track), no en la figura (pose-update denso a 500 = 78.9 ms). Reescrito remitiendo a la tabla. ✅
6. **Caption de `fig:wrong-family-matrix` lista de excepciones incompleta**: los off-diagonal >0.367 incluyen el token quadruped sobre filas de vehículos (0.386/0.462), no solo compact/articulated y lattice. Reescrito. ✅

Veredicto figura a figura: 14/14 figuras son reales, legibles y aportan (ningún placeholder ni texto rojo); las 3 de Blender son la novedad visual fuerte; pareto_neural y wrong_family son las de mayor valor argumental; probes_grid es cualitativa y ya se presenta como tal.

Recompilado: main 20 págs, 0 undefined, 3 overfull ≤12.9 pt.
