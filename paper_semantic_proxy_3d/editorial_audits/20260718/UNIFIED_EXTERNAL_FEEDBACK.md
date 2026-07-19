# FEEDBACK EXTERNO UNIFICADO — SPPA-MVFit (4 revisiones independientes)

**Fecha:** 2026-07-18
**Método:** 4 revisiones externas (F1: revisor doble ciego estilo Q1-aplicado/CV; F2: auditoría Q1/tribunal; F3: revisor Q1 journal; F4: evaluación con probabilidades por venue). Cada punto fue contrastado contra el paper (`semantic_proxy_3d_paper.tex`, 34 págs., 22 tablas), los artefactos sellados (`reproducibility/sppa_mvfit/`) y los resultados commiteados (`benchmarks/results/`) por 4 agentes de auditoría independientes (numérica, cobertura, viabilidad, estructura). Ningún punto se aceptó sin evidencia `archivo:línea`.

**Leyenda de veredicto:** ✅ CIERTO (el punto es válido) · ⚠️ PARCIAL (válido con matices / el revisor se equivoca en parte) · ❌ FALSO (el revisor se equivoca; se rebate con evidencia).

---

## A. TEMAS UNIFICADOS (14) — veredicto y acción

### T1. Evidencia 100% sintética/interna — el punto más votado
- **Quién:** F1-M5, F2-4.1, F3-§2, F4-P1 (los 4).
- **Veredicto:** ✅ CIERTO. Fuentes generadas por los autores, held-out propio, sin test externo.
- **Matiz de contrastación:** los revisores no sabían que **las corrupciones de máscara prerregistradas YA están medidas y selladas** (5 condiciones × 8 métodos × 240 actores = 9.600 filas en `raw_metrics.csv`; definidas en Enmienda 01 A5 y prerregistro §4). Solo falta publicarlas. Agregado verificado: SPPA clean 0.557 → mild 0.512 / moderate 0.418 / partial_occlusion 0.545 / mask_corruption 0.555; Generic 0.367 → 0.349/0.299/0.355/0.367. **El Δ se mantiene en 0.118–0.190 bajo todas las corrupciones (margen exigido: 0.030).**
- **Acción:** (a) publicar tabla de robustez sellada (coste: ~1 h, re-análisis, NO experimento nuevo); (b) añadir **mini-test externo con mallas reales** (ModelNet10 vía Princeton, red verificada; 30–60 mallas, mapeo clase→familia justificado, declarado "external sanity check"; coste 1.5–3 días de ingeniería); (c) framing: declarar el salto a real como trabajo futuro con evidencia puente (probes YOLOE).
- **Decisión del usuario:** D1 (ver §D).

### T2. H1 casi tautológico / grafo genérico indocumentado
- **Quién:** F1-M1 (el más duro), F3-§1, F4 ("baseline construido para perder").
- **Veredicto:** ✅ PARCIALMENTE CIERTO y es el punto intelectual más peligroso.
  - Contrastado: el grafo genérico (`graphs.json:66-75`) es **hand-crafted** (8 elipsoides simétricos; NO es la media de los 6 grafos de familia — verificado numéricamente — ni aleatorio) y **su construcción y autoría no están documentadas en ningún sitio**. La pregunta #1 de la defensa de F1 es válida y hoy no tiene respuesta escrita.
  - Contrastado: "SPPA sin ajustar (0.427) ya gana a Generic ajustado (0.367)" — **CIERTO** (`sppa_mvfit_method_means.tex:6-7`). La celda **Generic-sin-ajustar NO existe** (0 coincidencias en todo el repo); el 2×2 grafo×fitting está incompleto.
  - A favor nuestro: el margen +0.030 se fijó antes del test con análisis de potencia (Enmienda 01 A2: ~90 % potencia para +0.055 verdadero, SD pareada 0.12, n=240) — pero el paper no lo cita.
- **Acción:** (a) documentar construcción/autoría/criterio del grafo genérico (texto, honesto: diseñado por los autores como "8-slot plausible generic", simétrico, sin conocimiento de familia); (b) ejecutar celda Generic-nofit (trivial: `build_actor('generic', θ0)` contra GT ya liberado — ~1 h) → 2×2 completo que descompone grafo vs fitting; (c) **sensibilidad a la calidad del grafo genérico**: 2–3 grafos genéricos alternativos razonables, re-evaluar Δ (minutos de cómputo); (d) reencuadre honesto del titular: "el prior del grafo ya aporta más que todo el fitting del competidor; el fitting añade +0.130 encima" — esto convierte la debilidad en descomposición cuantificada; (e) citar la justificación del margen (texto).
- **Fase:** A (experimentos baratos) + B (texto).

### T3. Token de familia correcto regalado / familia errónea no medida
- **Quién:** F1-M3+Q4, F2-Q3, F3-preguntas, F4-P2.
- **Veredicto:** ✅ CIERTO. No existe matriz de confusión ni degradación por token erróneo (Threats lo declara fuera de alcance, `paper.tex:1580-1581`). Los `sppa_agnostic_*.json` miden otra cosa (invariancia del fitter agnóstico, que ignora etiquetas).
- **Acción:** ejecutar experimento de familia errónea sobre los 240 actores (token incorrecto aleatorio entre las 5 restantes; opcionalmente matriz 6×6). Código: soportado directamente (`infer_method` recibe `family` como argumento). Cómputo: ~70 s fitting + 1–2 min eval. Coste total 2–4 h. Etiquetado como análisis exploratorio post-hoc. **Es EL modo de fallo del método y es barato: se hace.**
- **Fase:** A.

### T4. Ruido de máscara / ablación top-only / ¿de dónde sale la vista lateral?
- **Quién:** F1-M3+Q5+Q6, F2-Q1, F3-§2 ("asunción de input irrealista"), F4.
- **Veredicto:** ⚠️ PARCIAL.
  - Ruido: ❌ FALSO que no exista — existe y está sellado (ver T1); el fallo es de **publicación**, no de evidencia.
  - Top-only: ✅ CIERTO que no existe. Cómputo trivial (~11 s fits; objetivo con peso 0 al término side + init top-only ~15 líneas).
  - Vista lateral desde UAV nadir: ✅ CIERTO que nunca se discute la adquisición (0 menciones). La pipeline real SPPA-OBS usa SOLO footprint nadir (`paper.tex:469-483`) — asimetría producción-vs-benchmark no discutida.
- **Acción:** (a) publicar tabla de corrupciones (T1); (b) ejecutar ablación top-only (~2–3 h); (c) párrafo honesto de adquisición: vista side requiere pasada oblicua/órbita o segunda plataforma; en operación nadir-pura el sistema degrada al camino footprint-only (que ya existe en producción) — enlaza con la ablación top-only como evidencia de ese modo degradado.
- **Fase:** A + B.

### T5. Tabla 6 (ola neural) = strawman / leaderboard encubierto
- **Quién:** F1-M4, F2-4.2, F3-§3.
- **Veredicto:** ✅ CIERTO en lo esencial. Los disclaimers existen, **pero la frase de victoria también existe** (`paper.tex:755-759`: "exceeds the measured neural generators ... by 0.330–0.433 while using 52×–5,767× fewer triangle equivalents, running 41×–208× faster ... payload ≈3.2×10⁴× smaller"). Los multiplicadores apilados son leaderboard puro. Además: Hunyuan es mini-turbo (no flagship), n=60, condición (b) fuera de distribución.
- **Acción:** (a) eliminar la frase de multiplicadores; (b) reencuadrar sección como **"input-modality mismatch demonstration"** (titular: qué ocurre cuando generadores image-to-3D reciben evidencia de telemetría); (c) nota de una línea: mini-turbo ≠ flagship, n=60, 2/240 crashes; (d) mantener tabla (los números son honestos y ya están publicados) pero con caption reescrito. F2 pedía borrarla: no se borra, se reencuadra — es evidencia de mismatch, útil para el argumento del hueco.
- **Fase:** B/C.

### T6. Bloat estructural: 34 págs. donde caben ~20
- **Quién:** F1-M7, F2-4.3, F3-§4, F4-P6/P9/P10 (los 4).
- **Veredicto:** ✅ CIERTO y cuantificado: **§10 "Secondary Systems Evidence" = 857 líneas = 52 % del tex = páginas 11–28 (18 de 34 págs.)**. 9 tablas (T9–T16, T19) giran sobre los mismos 4 probes YOLOE. 54 frases disclaimer (70 % en §10). §3 entera (~2 págs.) para decir que NO hay LLM en runtime. 10.3 legacy autodeclarado conservado a tamaño completo. Fila "Before alignment" = historia de desarrollo. Timestamps de replay (20260703T024800Z etc.) en el main.
- **Acción (poda):** mover §10.2–10.6 (+ minucias de protocolo de 10.1) al suplemento; fusionar T9+T19, T10+T14, T12+T13, T15+T16 → de 22 a 7–8 tablas en main; eliminar fila "Before alignment" y §10.3 (al suplemento); comprimir §3 LLM a 1 párrafo; dedup del pipeline (§3 enumera 5 pasos que duplican sec:pipeline; worked example narrado 3×; builder descrito 2×); recortar lenguaje defensivo a 1 disclaimer por sección + puntero a §13; abstract contextualiza latencia Unreal. **Main resultante: ~20–24 págs.** (decisión D4).
- **Fase:** C.

### T7. Visual Hull a 0.036 con ~43× menos coste: ¿para qué los roles?
- **Quién:** F1-minor5+Q8, F2-4.4, F3-§2, F4-P3.
- **Veredicto:** ✅ CIERTO (0.522@0.22 ms vs 0.557@9.43 ms). El "40×" no es afirmación del paper (ratio real 42.9×; el "41–208×" del texto es vs neuronales) — ❌ ese detalle de F1.
- **Acción:** (a) el valor diferencial real son roles + contrato de updates + payload: cuantificar con lo que ya existe (descriptor 1.45 kB vs 32.8 kB hull; update vs rebuild; yaw fallback) y con el nuevo experimento de familia errónea (T3: muestra cuándo el prior ayuda y cuándo daña — honestidad bidireccional); (b) argumento de utilidad operacional enlazado a SAGAT como estudio futuro (ya declarado `paper.tex:357-361`); (c) bajar el tono donde se insinúe superioridad de ocupación como fin. Role-aware IoU: ver D2.
- **Fase:** B (+A vía T3).

### T8. El título vende "fitting"; el fitting son 5 parámetros globales
- **Quién:** F1-M2; implícito en F3 ("optimizador trivial").
- **Veredicto:** ✅ CIERTO. θ = (log sx, log sy, log sz, s_sec, o_sec), compartidos por 8 slots, sin ajuste por parte (verificado en `sppa_mvfit.py:17,46,57-67`). El paper ya admite que el optimizador no es novedad.
- **Acción:** frase de alcance temprana y explícita: "el fitting es deliberadamente un alineamiento global de 5 parámetros; la contribución es la representación condicionada por familia + el contrato de runtime, no el optimizador". Decisión de retitular: D3.
- **Fase:** B.

### T9. Taxonomía interna inconsistente (15/23 arquetipos, 34/64/95 etiquetas, 6 familias)
- **Quién:** F1-M8.
- **Veredicto:** ✅ CIERTO. Cada número cuenta algo distinto (15 arquetipos+64 checks = contrato de recetas v0.3; 34 = regresión de cobertura del resolver; 23 arquetipos+95 etiquetas = manifiesto de recetas; 6 = familias del benchmark) y **ninguna tabla los reconcilia**; 15 vs 23 parece contradicción.
- **Acción:** tabla única de ontología (manifiesto ⊃ arquetipos ⊃ familias benchmark, con versión y fuente de cada cifra). Coste: 1 h, texto.
- **Fase:** B.

### T10. Métricas: falta superficie (Chamfer/F-score) y análisis de fallos
- **Quién:** F1-minor4+minor6, F3-preguntas.
- **Veredicto:** ⚠️ PARCIAL. **Chamfer ya está preregistrado, calculado por fila y agregado en dev** (SPPA 0.0088 vs Generic 0.0179) — nunca exportado al paper. F-score no existe (post-hoc 2–3 h). Fallos: tasa IoU<0.25 prerregistrada, nunca reportada; computada: **SPPA clean solo falla en lattice_tower (5/40; peores 0.147/0.148); el resto 0 fallos en 9.600 filas (100 % status pass)**. Traza completa de las 31 evaluaciones sellada (permite análisis de convergencia sin re-ejecutar).
- **Acción:** exportar Chamfer (1 h); F-score@τ voxel-superficie (2–3 h); subsección de análisis de fallos: peores casos por familia + por qué lattice_tower falla (estructura fina sub-voxel — hipótesis a verificar) + estadísticos de convergencia de la traza (1–2 h).
- **Fase:** A (cómputo) + B (texto).

### T11. Sensibilidad: resolución, candidatos, mix de familias
- **Quién:** F1-minor3+minor7+Q7, F2-Q1 (31 candidatos), F3.
- **Veredicto:** ⚠️ PARCIAL. Resolución: números EXISTEN y están sellados (Δ 0.198/0.197/0.188; |Δ|≤0.0094 < 0.015) — el paper solo dice PASS. Candidatos: sin barrido (esquema fijo 1+10k → presupuestos exactos 11/21/31/61; re-run 40–70 s). Mix: rider_cycle Δ=0.379 domina (~1/3 del agregado); **sin rider_cycle la media de las otras 5 familias = 0.152 > 0.030** — robustez del headline verificable por re-weighting (drop-one-family), nunca publicado. Justificación de las 6 familias: ausente.
- **Acción:** citar números de resolución (texto); barrido 11/21/31/61 (1–2 h); tabla drop-one-family (1 h); párrafo de selección de familias (cobertura morfológica: compacta/alargada/articulada/torre/persona/ciclista).
- **Fase:** A + B.

### T12. Posicionamiento: SMPL/3DMM ausente, Hydra, SuperDec no ejecutado, OBB ausente
- **Quién:** F1-M6+minor12+M3(OBB), F3-§5.
- **Veredicto:** ✅ CIERTO. SMPL/SMAL/3DMM: 0 citas. Hydra no por nombre (3D DSG sí, con posicionamiento). SuperDec/DualPrim/SuperFrusta citados pero sin statement de no-ejecución. OBB no existe como baseline.
- **Acción:** (a) párrafo SMPL/3DMM: mismo paradigma (plantilla paramétrica condicionada por categoría ajustada a evidencia), diferencia: contrato de runtime acotado + telemetría + roles; (b) párrafo Hydra/DSG: por qué contrato propio y no nodos en DSG existente; (c) statement explícito de no-ejecución de SuperDec/DualPrim (licencia/pesos/entrada RGB vs máscaras) + la ola neural externa ya cubre "métodos aprendidos"; (d) **baseline OBB** (cv2.minAreaRect sobre máscara top + extents z de side; voxelizado analítico; ~3–4 h) — es lo que producen los detectores 3D citados; barato y cierra el strawman del AABB.
- **Fase:** A (OBB) + B (texto).

### T13. Menores de precisión editorial (todos verificados)
- Hardware: paper dice solo "benchmark machine"; spec real en `pretest_freeze.json` (Zen 5, 32 CPU, Win 11, Py 3.12.6; RTX 5090 solo para neuronales) → añadir línea. [F1-minor2] ✅
- Abstract 9.4 ms sin contexto Unreal (17.8 ms P95 @100 obj) → contextualizar. [F1-minor2] ✅
- Checkpoint YOLOE: `yoloe-26s-seg.pt` en artefactos, no en el paper → añadir. [F1-minor9] ✅
- 3.09M tris (T6, media, top-mask) vs 1.7M máx (T8, preliminar superada) → línea explicativa. [F1-minor10] ✅ (condiciones distintas, ya declarado "preliminary/superseded")
- Holm "calculados pero no usados": la frase existe UNA vez (`paper.tex:1586-1587`), en §12 Threats → reescribir o eliminar. [F1-minor8] ⚠️ (existe pero no es el ruido repetido que F1 sugiere)
- 6 CIs secundarios sin ajustar → línea de declaración. [F1-minor11] ✅
- Enmiendas 03/05 fechadas antes de medir (03: 2026-07-16 = día del freeze; 05: 2026-07-17, oleada medida ese día) → declarar orden intra-día verificable solo por fecha; mantener. [F1] ✅ con matiz
- Referencias 2026: 8 entradas; **`chen2026sam3d` sin arXiv/eprint/url** → añadir identificador o marcar. [F1-minor9] ✅

### T14. Puntos F4 específicos
- "240 objetos es pequeño" → ❌ rebate: potencia ~90 % prerregistrada (Enmienda 01 A2); n justificado por diseño, no por convención de CV.
- "LLM distrae / quitar del título conceptual" → ⚠️ el LLM NO está en título ni abstract (F4 se equivoca); §3 se comprime a 1 párrafo (T6).
- "La contribución cuesta entenderla" → ✅ ya mitigado: nueva subsección `sec:pipeline` (2 caminos, 1 builder, worked example) integrada 2026-07-18.
- "Dos papers en uno" → ✅ pivote en línea 677; la poda T6 lo resuelve (deployment condensado a 1–2 págs.).

---

## B. ERRORES DE LOS REVISORES (a rebatir, NO a implementar)

1. **F2: "14 páginas y 22 tablas"** — el paper tiene 34 páginas (22 tablas sí). Indica lectura de versión distinta o descuido.
2. **F1: atribuye al paper un "40×" vs visual hull** — el paper no lo afirma; ratio real 42.9× y el "41–208×" es vs generadores neuronales.
3. **F1-M3: "las corrupciones se mencionan pero no hay resultados"** — los resultados existen y están sellados (9.600 filas, 5 condiciones); falta publicarlos, no medirlos. El framing correcto: "no publicados en el manuscrito".
4. **F4: "quitar el LLM del título"** — el título no menciona LLM.
5. **F2: "eliminar la Tabla 6"** — desproporcionado; con reencuadre a modality-mismatch es evidencia útil del hueco metodológico.
6. **F2/F3 sugieren que IoU de voxel penaliza injustamente a los generadores neuronales** — matiz: la alineación a escala/centro/yaw GT ya se hizo (declarada); la penalización real es la máscara 96×96 OOD, que es exactamente el punto del experimento (mismatch de modalidad), no un defecto a ocultar.

## C. LO QUE LOS 4 COINCIDEN QUE ES FORTALEZA (proteger en la poda)

- Prerregistro + sellado + semillas NIST + bootstrap CIs: "por encima del 95 % de lo publicado" (F1), "excepcional" (F2), "ejemplar" (F3), "muy por encima del típico" (F4).
- Aislamiento de variable única en H1 (mismo optimizador/presupuesto/inputs).
- Claim Boundaries (§13) y honestidad de fracasos propios.
- El contrato de runtime (descriptor/update, fallback, yaw ambiguo) como contribución real (F1 lo dice explícito: "probablemente la contribución real").
- Originalidad del hueco (F4: 9/10).

## D. DECISIONES PARA EL USUARIO

- **D1. Mini-test externo (ModelNet10, 30–60 mallas reales → siluetas → SPPA):** el añadido que más sube la probabilidad de aceptación (los 4 lo exigen). Coste 1.5–3 días de trabajo agente. Declarado "external sanity check" secundario. ¿SÍ/NO?
- **D2. Role-aware IoU:** las fuentes CSG no guardan etiquetas de parte → solo sería posible con mapeo posicional slot↔componente hecho a mano, post-hoc (4–8 h, riesgo de parecer ad-hoc). Recomendación: **NO hacerlo**; justificar en texto (roles validados indirectamente vía experimento de familia errónea + contrato) y dejarlo como future work con diseño prerregistrado. ¿OK?
- **D3. Título:** mantener "Family-Conditioned Multiview Fitting..." + frase de alcance temprana (recomendado, el fitting sí existe y está prerregistrado) vs retitular hacia priors/contrato. ¿Cuál?
- **D4. Objetivo de poda:** agresiva (~18–20 págs. main) vs conservadora (~22–24 págs., mantiene tabla fusionada de probes + runtime reducido en main). Recomendación: **conservadora** (venue aplicado valora el contexto de despliegue). ¿OK?

## D-RES. DECISIONES DEL USUARIO (2026-07-18, "lo más ambicioso y honesto")

- **D1 = SÍ:** mini-test externo con mallas reales, declarado "external sanity check" exploratorio.
- **D2 = SÍ, con salvaguarda:** role-aware IoU se hace, pero el mapeo slot↔componente se congela por escrito (`ROLE_MAPPING_FROZEN.md`) ANTES de computar ningún número; resultado declarado descriptivo-exploratorio, se reporte lo que se reporte (incluso si es malo).
- **D3 = mantener título** + frase de alcance explícita temprana (el fitting existe, está prerregistrado; la frase declara que es un alineamiento global deliberadamente simple y que la contribución es la representación + contrato).
- **D4 = poda agresiva:** main objetivo ~18–20 páginas; §10.x al suplemento salvo condensado de 1–2 páginas.

## E. ORDEN DE IMPLEMENTACIÓN (tras decisiones)

- **Fase A — Evidencia nueva (post-hoc, etiquetada exploratoria, FUERA del sello, carpeta `benchmarks/mvfit_reviewer_experiments/`):** A1 Generic-nofit (2×2) · A2 familia errónea · A3 top-only · A4 OBB baseline · A5 barrido candidatos 11/21/31/61 · A6 exportar tabla corrupciones selladas · A7 Chamfer export + F-score · A8 análisis de fallos + convergencia · A9 drop-one-family · A10 sensibilidad grafo genérico (2–3 variantes) · [A11 externo ModelNet si D1=SÍ]. Cómputo total: minutos; ingeniería: ~2 días (+1.5–3 días si A11).
- **Fase B — Texto main:** construcción/autoría grafo genérico · justificación margen+potencia · spec hardware · números resolución · checkpoint YOLOE · nota mini-turbo · línea 3.09M/1.7M · Holm · CIs secundarios · párrafos SMPL/3DMM, Hydra/DSG, SuperDec-no-ejecución · adquisición vista lateral · selección de familias · abstract latencia · alcance del fitting (T8) · tabla ontología (T9) · reencuadre Tabla 6 (T5) · reencuadre titular 2×2 (T2d).
- **Fase C — Poda estructural:** §10.2–10.6 a suplemento · fusiones de tablas · eliminar "Before alignment" y §10.3 legacy · §3 LLM a 1 párrafo · dedup pipeline · recorte defensivo (1 por sección + puntero §13) · eliminar frase de multiplicadores.
- **Fase D — Cierre:** recompilar · puerta strict · tribunal R5 focalizado · handoff `kimi_code.md` · commit (con confirmación).
