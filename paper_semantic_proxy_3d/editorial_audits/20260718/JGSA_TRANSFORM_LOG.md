# JGSA TRANSFORM LOG — 2026-07-18

Transformación "JGSA-fit" ejecutada sobre `semantic_proxy_3d_paper.tex` (main) y
`semantic_proxy_3d_submission_supplement.tex` (suplemento). Sin git commit.
`reproducibility/` intacto. Ningún número cambiado; ningún `\label` de tabla
`\input` renombrado.

**Nota de línea base:** el main recibido ya venía podado (1240 líneas, 14
secciones, 18 tablas, 3 figuras, 24 págs. aprox.); los conteos "antes" de este
log son sobre ese estado, no sobre el de 34 páginas del informe estructural.

---

## 1. Resultado final (verificado por compilación)

| Documento | Páginas | Secciones | Tablas | Figuras | Errores | Undefined |
|---|---|---|---|---|---|---|
| Main (`sppa_check.pdf`) | **19** | 6 numeradas + Data/Code Availability | **6** | **14** | 0 | 0 |
| Suplemento (`supp_check.pdf`) | **9** | S.1–S.9 + front matter | **23** | 1 | 0 | 0 |

- Ciclo ejecutado: `pdflatex → bibtex → pdflatex × 2` con
  `-jobname=sppa_check` (main, compilado ANTES) y `-jobname=supp_check`
  (suplemento, `xr-hyper` resuelve `main-sec:*` y `main-tab:*` sin undefined).
- Abstract reescrito: **206 palabras**, una sola ocurrencia de "not claimed"
  (la frase externa exigida por la spec, con los cuatro números: SPPA 0.413,
  generic 0.370, capsule 0.492, visual hull 0.656).
- Figuras del main (14, todas referenciadas; placeholders ya existentes):
  fig_pipeline_overview (la antigua Fig 1, conservada), fig_family_graphs_blender,
  fig_role_colored_blender, fig_fitting_sequence_blender, fig_h1_by_family,
  fig_robustness_conditions, fig_2x2_decomposition, fig_wrong_family_matrix,
  fig_view_ablation, fig_external_scatter, fig_external_gallery (la antigua
  Fig 3, conservada), fig_pareto_neural, fig_probes_grid, fig_runtime_scaling.
  Dos pares van en minipages dentro del mismo float (h1_by_family +
  robustness_conditions; wrong_family_matrix + view_ablation) por economía de
  páginas; las 14 conservan caption y número propios.

## 2. Mapa antes/después de secciones (main)

| Antes (14) | Después (6 + 2) |
|---|---|
| §1 Introduction | **1 Introduction** (fusiona §1+§2; párrafo de encuadre geoespacial/twin promovido a apertura; bullets de "secondary contributions" eliminados) |
| §2 Contribution and Scope | → §1 (contribución + alcance en prosa) |
| §3 SPPA Contract | **3 Materials and Methods** (3.1 contract+part graph; LLM → 2 frases; tabla ontología ELIMINADA) |
| §4 Related Work | **2 Related Work** (dump de generadores → 2 líneas con refs agrupadas; párrafo "cited but not executed" eliminado; SAGAT/TLX → 1 frase en future work de Discussion) |
| §5 Family-Conditioned SPPA-MVFit | 3.4 Confirmatory protocol (lenguaje sobrio: "preregistered and sealed before evaluation"; hardware → 1 línea; bookkeeping Amendment/NIST/triple-role → suplemento) |
| — | 3.5 Evaluation data (benchmark 240 + 52 mallas externas + 4 probes) |
| §6 Primary Results | **4 Results** (4.1–4.8) |
| §7 Robustness and Boundary Conditions | → 4.2–4.5 |
| §8 External Sanity Check | → 4.6 (con tabla + scatter + gallery) |
| §9 External Neural Comparison | → 4.7 (~10 líneas + fig_pareto_neural; reconciliación 3.09M/1.7M eliminada; "expected reviewer question" eliminado) |
| §10 Real-Image Probes and Deployment | → 4.8 (2 párrafos + tabla runtime condensada + fig_probes_grid + fig_runtime_scaling; tabla probes al suplemento) |
| §11 Discussion | **5 Discussion** (fusiona §11+§12+§13; incluye tensión nadir/side-view y autoría compartida de grafos en tono sobrio) |
| §12 Threats to Validity | → §5 (amenazas en prosa, `\label{sec:threats}` conservado) |
| §13 Claim Boundaries | ELIMINADA como sección → 3 frases de frontera dentro de §5 |
| §14 Conclusion | **6 Conclusion** (≈ la mitad; sin "honest") |
| Data and Code Availability | **Data Availability** + **Code Availability** separadas |

Decisión de estructura: se fusionaron "Materials and Methods" + "Method" en un
**Materials and Methods unitario** (opción explícita de la spec), por lo que el
main tiene **6 secciones numeradas** en lugar de 7; JGSA publica 5–7.

## 3. Tabla de tablas (main: 18 → 6 conservadas, 9 movidas, 2 condensadas, 1 eliminada)

| Tabla | Destino |
|---|---|
| tab:mvfit-h1 (H1 summary) | **Main §4.1** |
| tab:mvfit-means (costes) | **Main §4.1** |
| tab:mvfit-secondary | **Main §4.1** |
| tab:surface-metrics | **Main §4.2** |
| tab:external-sanity | **Main §4.6** |
| tab:deployment-runtime-summary | **Main §4.8** |
| tab:robustness-conditions | Suplemento S.9 (figura fig_robustness_conditions en main) |
| tab:mvfit-family-strata | Suplemento S.9 (figura fig_h1_by_family en main) |
| tab:graph-x-fitting | Suplemento S.9 (figura fig_2x2_decomposition en main) |
| tab:drop-one-family | Suplemento S.9 (rango 0.152–0.214 inline en §3.5) |
| tab:wrong-family-matrix | Suplemento S.9 (figura fig_wrong_family_matrix en main) |
| tab:view-ablation | Suplemento S.9 (figura fig_view_ablation en main) |
| tab:generic-graph-sensitivity | Suplemento S.9 |
| tab:neural-external-wave | Suplemento S.2 (figura fig_pareto_neural en main) |
| tab:real-probe-summary | Suplemento S.4 (figura fig_probes_grid en main) |
| tab:obb-baseline | **Condensada inline** (§4.5: 0.252 vs 0.248, −0.004 CI, +0.306 CI) |
| tab:role-aware-iou | **Condensada inline** (§4.5: 0.545/0.319 vs 0.053/0.017, +0.265 CI, 920 pares) |
| tab:ontology-counts | **ELIMINADA con sus conteos** (autorizado por spec; queda 1 frase de cobertura del manifiesto en §3.1) |

Todos los `\label` de tablas `\input` se conservaron exactos en su nueva
ubicación (los scripts `export_paper_tables.py` los siguen encontrando).

## 4. Cortes del suplemento (21 → 9 páginas)

- **ELIMINADO:** S.4 OBJ Construction Sanity Check (legacy) — sección completa.
- **ELIMINADO → nota de 5 líneas (S.7):** stress test de sustitución
  (tabla sota-stress-test + figura input-alignment-grid + prosa de elegibilidad)
  con puntero a la neural wave (S.2).
- **ELIMINADO → nota (S.6):** tablas round-trip con error 0.000 (contract
  benchmark 6 casos y bbox-vs-silhouette 162 máscaras); queda 1 párrafo que las
  declara regresiones de plumbing en el artefacto.
- **ELIMINADO → 1 párrafo (S.4):** batería anti-shortcut (tabla), diario de
  conectores (tabla) y visual-bridge (tabla visual-part-evidence + figuras
  visual-part-evidence y agnostic probe); caption y texto condensados.
- **SHA-256:** los 4 hashes explícitos → 1 línea que apunta al manifiesto del
  artefacto (`reproducibility/sppa_mvfit/`).
- **S.3 open-label:** divagaciones del párrafo quadruped recortadas (~50 %).
- **S.8 Unreal:** prosa condensada (~50 %); tabla unreal-selected conservada
  completa (condensada a scriptsize).
- **Figuras:** queda 1 esencial (input-mode ablation grid); la grid de probes
  vive ahora en el main (fig_probes_grid); zoom-audit eliminada.
- **Recibió del main:** 9 tablas (ver §3) insertadas con orden y captions
  sobrias (S.2 neural, S.4 probes, S.9 análisis).
- Medidas de página para llegar a <10: márgenes 0.72in, `\linespread{0.94}`,
  floats `[!htbp]` en S.9, captions compactos.

## 5. Metalenguaje (grep antes → después)

| Término | Main antes | Main después | Supp. antes | Supp. después | Regla |
|---|---|---|---|---|---|
| honest/honestly | 3 | **0** | 1 | **0** | 0 ✓ |
| expected reviewer question | 1 | **0** | 0 | **0** | 0 ✓ |
| "It should not." | 1 | **0** | 0 | **0** | reescrita ✓ |
| \textcolor{red} | 0 | **0** | 0 | **0** | 0 ✓ |
| sealed | 41 | **2** (solo §3.4) | 14 | **1** | ≤6 ✓ |
| preregistered | 18 | **8** | 3 | **1** | ≤8 ✓ |
| Amendment (IDs) | 7 | **0 IDs** (2 menciones genéricas) | 1 | 5 (S.2/bookkeeping de protocolo) | IDs solo Methods/protocolo ✓ |
| triple-role | 0 | **0** | 0 | 1 (bookkeeping) | fuera de Methods/main 0 ✓ |
| not claimed | 2 | 2 | 0 | 0 | 1 = frase externa exigida; 1 = alcance del optimizador |

## 6. Aparato prerregistrado y tono

- Se describe **una sola vez** en Methods (§3.4): margen, potencia (~90 %,
  n=240), bootstrap, "preregistered and sealed before evaluation", hashes antes
  de GT privada. Eliminadas las re-narraciones en Results/Discussion.
- Amendment~01/03/05, NIST beacon y triple-role release viven solo en el
  suplemento (front matter "Protocol bookkeeping" + S.2).
- Máximo ~1 mención de límites por sección del main; Discussion concentra el
  resto.

## 7. Desviaciones de la especificación

1. **6 secciones numeradas** en lugar de 7 (la spec autorizaba fusionar
   3+4 en Materials and Methods unitario: aplicado).
2. **Main en 19 páginas** (objetivo ~17–19: en el borde superior, dependiente
   de los placeholders; las figuras finales pueden mover ±1 página).
3. **OBB y role-aware-IoU** no se movieron como tabla: condensadas inline con
   todos sus números clave (opción autorizada por la regla dura 1); sus archivos
   `\input` siguen en disco, sin referenciar.
4. **Suplemento con 1 figura** (input-mode ablation); la grid de probes esencial
   está en el main (fig_probes_grid) y la zoom-audit se eliminó como
   redundante. Si el board quiere más figuras de probes en el suplemento, hay
   margen de página para reintroducir la zoom-audit.
5. **Conteos 23 arquetipos/95 etiquetas** se conservan como UNA frase de
   cobertura del manifiesto en §3.1 (scope del resolver); la tabla de
   reconciliación y los conteos 15/64 y 34 sí se eliminaron con la tabla.
6. Bibliografía del main a `\footnotesize` por economía de página.
7. **Code Availability:** no existe URL declarable en el repo (verificado:
   sin `git remote`, sin GitHub/Zenodo en README/RELEASE_MANIFEST) →
   "available upon publication", sin URL inventada.

## 8. Propuesta de título (NO aplicada)

El actual se conserva por ser descriptivo. Variante más legible para JGSA
(jerga "SPPA-MVFit" movida al abstract/keywords):

> **"Family-conditioned multiview fitting of semantic primitive proxies for
> dynamic objects in UAV digital twins"**

Pone el objeto geográfico (dynamic objects, UAV digital twins) por delante del
método y elimina el acrónimo del título. No aplicada a la espera de decisión.

## 9. Verificación final

- `sppa_check.pdf`: 19 páginas, 0 errores, 0 undefined references/citations.
- `supp_check.pdf`: 9 páginas, 0 errores, 0 undefined (xr-hyper resuelto
  contra el nuevo `sppa_check.aux`).
- BibTeX: 0 errores en ambos (0 warnings de entradas faltantes).
