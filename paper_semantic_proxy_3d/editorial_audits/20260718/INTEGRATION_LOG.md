# INTEGRATION LOG — Nueva evidencia + correcciones de texto (post-poda)

**Fecha:** 2026-07-18
**Documentos:** `semantic_proxy_3d_paper.tex` (main) · `semantic_proxy_3d_submission_supplement.tex` (suplemento) · `semantic_proxy_3d_references.bib`
**Copia de trabajo:** `D:\Deep-AeroTwin-UE57-Test\sppa_integration_work\` (el repo canónico `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d` NO fue modificado; sin git commit; `reproducibility\sppa_mvfit\` intacto — solo lectura de `pretest_freeze.json` para verificar hardware).
**Contexto aplicado:** `UNIFIED_EXTERNAL_FEEDBACK.md` (T1–T14, D-RES) · `PRUNE_LOG.md` (estado post-poda).

---

## 1. Compilación final (objetivo cumplido)

```
main:  pdflatex -jobname=sppa_check → bibtex sppa_check → pdflatex ×3
       Output written on sppa_check.pdf (24 pages). 0 errores, 0 undefined, 0 LaTeX warnings.
supp:  pdflatex -jobname=supp_check → bibtex supp_check → pdflatex ×3 (DESPUÉS del main; xr lee sppa_check.aux)
       Output written on supp_check.pdf (21 pages). 0 errores, 0 undefined, 0 LaTeX warnings.
```

| Documento | Antes | Después |
|---|---|---|
| Main: páginas | 16 | **24** (dentro del límite ~24; no fue necesario mover tablas por espacio — regla 5 no activada) |
| Main: tablas | 7 | **18** (11 nuevas) |
| Main: figuras | 2 | 3 (nueva Fig. 3 cualitativa externa) |
| Suplemento: páginas | 19 | **21** |
| Suplemento: tablas | 14 (S1–S14) | **20** (S15–S20 nuevas) |

Referencias cruzadas verificadas: `\ref{main-sec:neural-external-wave}` en el suplemento renderiza "Section 9" (renumeración propagada vía xr-hyper); `main-sec:pipeline` → 3.x. 0 undefined en ambos.

## 2. Mapa final de secciones del main (14)

1. Introduction
2. Contribution and Scope
3. SPPA Contract — 3.1 Part Graph · 3.2 Pose, Yaw, and Updates · 3.3 End-to-End Pipeline (`sec:pipeline`) · 3.4 Descriptor and Runtime Backend · **Tabla 1 ontología (E6)**
4. Related Work — **+ párrafo SMPL/SMAL/3DMM (E5) · + Hydra (E5) · + no-ejecución SuperDec/DualPrim/SuperFrusta (E5)**
5. Family-Conditioned SPPA-MVFit (`sec:mvfit`) — **+ alcance del fitting (E4) · + construcción/autoría grafo genérico (E1) · + justificación margen+potencia+resolución (E2) · + selección de familias + Tabla 2 drop-one (E8) · + hardware (E3)**
6. Primary Results (`sec:primary-results`) — **+ Tabla 4 robustez prerregistrada (A) · + Tabla 8 descomposición 2×2 (B) · + análisis de fallos + Tabla 9 superficie (E9) · + línea ICs no ajustados (E14)**
7. **Robustness and Boundary Conditions (NUEVA, `sec:robustness-boundary`)** — 7.1 Wrong-Family Token · 7.2 View Ablation and Side-View Acquisition (E7) · 7.3 OBB Baseline · 7.4 Generic-Graph Design Sensitivity · 7.5 Optimizer Budget Sweep · 7.6 Role-Aware IoU
8. **External Sanity Check (Real Meshes) (NUEVA, `sec:external-sanity`)** — Tabla 15 + Fig. 3
9. External Neural Comparison (Input-Modality Mismatch) (`sec:neural-external-wave`) — era §7
10. Real-Image Probes and Deployment Summary (`sec:deployment-summary`) — era §8 · **+ checkpoint YOLOE (E10)**
11. Discussion — era §9
12. Threats to Validity (`sec:threats`) — era §10 · **7 amenazas (E11)**
13. Claim Boundaries (`sec:claim-boundaries`) — era §11 · **+ boundary externa (E12)**
14. Conclusion — era §12 · **+ calibración (E12)**

## 3. Tablas nuevas integradas (ruta de cada `\input`)

### Main (11 nuevas; números = numeración final)

| # | Label | Fragmento `\input` | Pieza |
|---|---|---|---|
| T1 | `tab:ontology-counts` | (escrita a mano en el tex; números del propio paper: 15+64 / 34 / 23+95 / 6) | E6 |
| T2 | `tab:drop-one-family` | `benchmarks/mvfit_posthoc_analysis/t5_drop_one_family/drop_one_family_table.tex` | E8 |
| T4 | `tab:robustness-conditions` | `benchmarks/mvfit_posthoc_analysis/t1_robustness/robustness_conditions_table.tex` | **A** |
| T8 | `tab:graph-x-fitting` | `benchmarks/mvfit_posthoc_analysis/t2_graph_x_fitting/graph_x_fitting_2x2_table.tex` | **B** |
| T9 | `tab:surface-metrics` | `benchmarks/mvfit_posthoc_analysis/t3_surface/surface_metrics_table.tex` | E9 |
| T10 | `tab:wrong-family-matrix` | `benchmarks/mvfit_reviewer_experiments/e1_wrong_family/wrong_family_matrix.tex` | **C1** |
| T11 | `tab:view-ablation` | `benchmarks/mvfit_reviewer_experiments/e2_top_only/top_only_ablation_table.tex` | C2 |
| T12 | `tab:obb-baseline` | `benchmarks/mvfit_reviewer_experiments/e3_obb/obb_baseline_table.tex` | C3 |
| T13 | `tab:generic-graph-sensitivity` | `benchmarks/mvfit_reviewer_experiments/e5_generic_variants/generic_graph_sensitivity_table.tex` | C4 |
| T14 | `tab:role-aware-iou` | `benchmarks/mvfit_reviewer_experiments/e6_role_aware/role_aware_iou_table.tex` | C6 |
| T15 | `tab:external-sanity` | `benchmarks/external_mesh_sanity/external_sanity_table.tex` | **D** |

### Suplemento, nueva sección **S8 "Post-Hoc Robustness and Boundary Analyses (Supplementary Tables)"** (`sec:supp-posthoc`)

| # | Label | Fragmento `\input` | Contenido |
|---|---|---|---|
| S15 | `tab:supp-robustness-all-methods` | `benchmarks/mvfit_posthoc_analysis/t1_robustness/robustness_conditions_all_methods_table.tex` | 8 métodos × 5 condiciones (sellado) |
| S16 | `tab:supp-graph-fitting-effects` | `benchmarks/mvfit_posthoc_analysis/t2_graph_x_fitting/graph_x_fitting_effects_table.tex` | efectos 2×2 + estratos |
| S17 | `tab:supp-chamfer-conditions` | `benchmarks/mvfit_posthoc_analysis/t3_surface/chamfer_conditions_table.tex` | Chamfer por condición |
| S18 | `tab:supp-worst-cases` | `benchmarks/mvfit_posthoc_analysis/t4_failures/worst_cases_table.tex` | 10 peores casos |
| S19 | `tab:supp-budget-sweep` | `benchmarks/mvfit_reviewer_experiments/e4_budget/budget_sweep_table.tex` | barrido 11/21/31/61 |
| S20 | `tab:supp-wrong-family-comparisons` | `benchmarks/mvfit_reviewer_experiments/e1_wrong_family/wrong_family_comparisons.tex` | deltas pareados wrong/correct/generic |

**Quedó en suplemento (número clave en prosa del main):** barrido de presupuesto (C5: prosa en §7.5 con 11/21/31/61 y +0.003 n.s.), peores casos (E9: prosa con 5/240, 0.147/0.148), Chamfer por condición (E9: prosa con clean 0.008/0.009/0.016), efectos 2×2 por estrato (B: prosa con efectos pooled), all-methods por condición (A), comparaciones pareadas wrong-family (C1).

**Figura nueva:** `figures/external_sanity_qualitative.png` (composite 2 paneles generado desde `benchmarks/external_mesh_sanity/qualitative/compact_vehicle-modelnet40-car-00.png` [éxito: SPPA 0.628 vs generic 0.397] + `lattice_tower-objaverse-water_tower-02.png` [fallo: mismatch plantilla vertical vs instancia horizontal]) → Fig. 3 del main (D, punto "una figura cualitativa").

## 4. Cambios de texto por punto E1–E14

- **E1 (§5.1):** párrafo de construcción del grafo genérico: diseñado por los autores como prior plausible de 8 slots (elipsoides simétricos, sin conocimiento de familia, hand-crafted, no aprendido, no aleatorio, no media de las 6 familias), congelado antes del benchmark; remite a §7.4 (sensibilidad) y §12 Threats (autoría compartida declarada como limitación).
- **E2 (§5.2):** margen +0.030 fijado 2026-07-15 antes del test sellado; supera la sensibilidad de un voxel de borde en 64³ (Enmienda 01 A2/A7 — verificado en `SPPA_PROTOCOL_AMENDMENT_01_20260715.md`: "larger than the expected one-voxel boundary sensitivity established by the resolution check in A7"); potencia ~90% para efecto verdadero +0.055 con SD pareada 0.12 y n=240 (A2, verbatim verificado); números de resolución sellados Δ 0.198/0.197/0.188 en 48/64/80³, |Δ|≤0.0094 < 0.015. La frase de §6 sobre el resolution check se actualizó para citar el umbral y remitir a §5.
- **E3 (§5.2):** estación AMD Zen 5, 32 CPUs lógicos, Windows 11, CPython 3.12.6 (verificado contra `reproducibility/sppa_mvfit/pretest_freeze.json` — solo lectura); corridas neurales en RTX 5090 32 GB; CPU del fitter reportada aparte.
- **E4 (§5.1):** "The fitter is deliberately a five-parameter global alignment shared by all slots; the contribution is the family-conditioned representation and the runtime contract, not the optimizer."
- **E5 (§4):** párrafo SMPL/SMAL/3DMM (mismo paradigma de plantilla paramétrica condicionada por categoría; diferencia: contrato de runtime acotado + telemetría + roles + gemelos UAV); Hydra añadido al párrafo de scene graphs (contrato propio = display actor ligero, no sustrato de mapping); statement de no-ejecución de SuperDec/DualPrim/SuperFrusta (entrada RGB/shape completa vs máscaras de telemetría; pesos/licencias; la ola neural de §9 cubre métodos aprendidos). **.bib:** `loper2015smpl` (ACM TOG 34(6), doi:10.1145/2816795.2818013), `blanz1999morphable` (SIGGRAPH 1999, doi:10.1145/311535.311556), `zuffi2017smal` (CVPR 2017, doi:10.1109/CVPR.2017.523), `hughes2022hydra` (RSS 2022, doi:10.15607/RSS.2022.XVIII.007). bibtex: 0 errores, las 4 resuelven.
- **E6 (§3):** Tabla 1 de ontología + frase reconciliadora (familias ⊂ arquetipos revisados ⊂ manifiesto versionado): contrato v0.3 = 15 arquetipos + 64 checks; regresión del resolver = 34 etiquetas; manifiesto = 23 arquetipos + 95 etiquetas; benchmark = 6 familias.
- **E7 (§7.2):** párrafo de adquisición de la vista side (no existe desde nadir puro; requiere pasada oblicua/órbita o segunda plataforma; la pipeline operativa ya corre en modo nadir footprint-only en producción; la ablación top-only cuantifica ese modo degradado).
- **E8 (§5.2):** justificación de las 6 familias por cobertura morfológica + drop-one-family (Tabla 2): rango 0.152 (sin rider_cycle) – 0.214 (sin compact_vehicle), siempre > 0.030.
- **E9 (§6):** párrafo de análisis de fallos: 5/240 fallos (IoU<0.25), todos lattice_tower csg_id (5/40 de la familia; peores 0.147/0.148); espesores sub-voxel 0.09–0.23 u.m. vs celda 0.15×0.10×0.10 (verificado en `failure_analysis.json`: `voxel_cell_world_units` y `lattice_tower_inspection`); los 8 métodos ≤0.24 en esos actores (hull ≤0.43) — efecto de resolución compartido. Convergencia: 88.7% SPPA mejora en el último barrido (0.8875 en `convergence_stats.json`); θ en cota: SPPA 0% vs genérico 57.9% (0.5792). Superficie: Chamfer 0.008/0.009/0.016; F-score@1.5vox 0.831/0.799/0.560 (Tabla 9).
- **E10 (§10, deployment):** "(checkpoint `yoloe-26s-seg.pt`)" donde se menciona el detector.
- **E11 (§12 Threats):** el ítem que declaraba familia-errónea fuera de alcance **ya no existía** en la versión podada (la poda eliminó/fusionó ese ítem; las 5 amenazas actuales no lo contienen — nada que borrar). Añadidas amenaza 6ª (distribución externa, §8) y 7ª (autoría compartida de grafos, E1).
- **E12:** Abstract: frase añadida verbatim tras los resultados internos ("A post-hoc external sanity check on 52 real meshes … occupancy leadership outside the design distribution is not claimed."). Claim Boundaries: ítem "Not supported" análogo con números. Conclusion: párrafo de calibración (contrato/roles/updates como contribución durable; envelope cuantificado dentro de la distribución de diseño).
- **E13 (.bib):** `chen2026sam3d` → `note={to appear; identifier pending verification}`. Revisadas las demás entradas 2026: `hunyuan2026hy3dbench`, `li2026pixal3d`, `yang2026p3dbench` (arXiv url), `hu2026sam3danimal` (doi+url), `ganeshan2026superfrusta`, `meng2026dualprim` (CVF url), `hyper3d2026rodin25`, `epic2026nanite`, `pytorch2026memoryfraction` (url+note) — todas con identificador.
- **E14 (§6):** línea en prosa: los ICs secundarios de la tabla de deltas son per-comparison y no se ajustan por multiplicidad; la inferencia confirmatoria es solo H1; efectos grandes relativos a sus anchos de intervalo.

## 5. Etiquetado de evidencia (regla 3)

- Tabla de corrupciones (T4): caption "preregistered observation conditions, sealed with the confirmatory run and reported here in full" + remisión a Enmienda 01 A5; NO etiquetada post-hoc.
- "post-hoc exploratory analysis" aparece **exactamente 4 veces** en el main (una por sección): §5 (drop-one), §6 (descomposición 2×2), §7 (declaración única al inicio de la sección que cubre C1–C6), §8 (sanity check). Captions de §§5–8 deduplicados del prefijo repetido.
- Suplemento S8: declaración única en el preámbulo de la sección; caption de S15 marcada como sellada (no post-hoc).

## 6. Discrepancias fragmento vs brief (SE USÓ EL FRAGMENTO; no inventadas)

1. **Robustez mask_corruption Δ CI:** fragmento `robustness_conditions_table.tex` = 0.189 **[0.179, 0.197]**; brief decía [0.180, 0.198] (y `SUMMARY.md` también). Tabla va por `\input` verbatim → queda [0.179, 0.197]. En prosa solo se cita Δ=0.189 (sin CI), sin conflicto.
2. **Side-only Δ CI:** fragmento `top_only_ablation_table.tex` = −0.012 [−0.021, **−0.003**]; brief y `e2_top_only/README.md` decían −0.004. Prosa del main usa el fragmento: [−0.021, −0.003].
3. **G3 Δ sensibilidad genérica:** fragmento `generic_graph_sensitivity_table.tex` = **0.275** [0.266, 0.285]; brief y `e5 README.md` decían 0.276. Tabla por `\input` verbatim → 0.275. La prosa no cita el Δ de G3 individualmente.
4. **CLASS_MAPPING.md** declara "total target 49 meshes" pero el resultado final sellado es n=52 (tabla, JSON y brief concuerdan en 52); se usa 52.

Sin otras discrepancias: todos los demás números del brief verificados contra fragmentos `.tex`, JSONs (`external_sanity.json`, `role_aware_iou.json`, `convergence_stats.json`, `failure_analysis.json`) y READMEs de `mvfit_reviewer_experiments/`.

## 7. Incidencias durante la integración (resueltas)

1. **Encabezado de sección consumido en una edición:** al insertar §7+§8, el `old_string` incluyó `\section{External Neural Comparison...}`; se restauró inmediatamente con su `\label` y se verificó en la compilación (§9 presente, xr del suplemento resuelve "Section 9").
2. **Warning float en suplemento:** dos tablas preexistentes con `[h]` (S5.1 y S7) generaban `` `h' float specifier changed to `ht' `` tras el desplazamiento de 2 líneas del Purpose; cambiadas a `[H]` (consistente con el resto del documento) → 0 warnings.
3. **CRLF:** el main es CRLF puro; los reemplazos multi-línea se hicieron con `\r\n` explícito; finales preservados.
4. **MiKTeX aviso "User/administrator updates are out-of-sync"**: mensaje de la distribución, no del documento; no afecta a errores/referencias.

## 8. Verificación final de contenido (PDF renderizado)

Spot-check sobre `sppa_check.pdf` (texto extraído): presentes 0.118 (moderate), 0.180 (Generic-nofit), 0.248 (efecto grafo), 0.205 (wrong token), 0.458 (top-only), 0.252 (OBB), 0.282 (G3), 0.319 (role IoU), 0.413/0.656 (externo), giraffe-horse OOD, `yoloe-26s-seg.pt`, SMPL, Hydra, Zen 5, potencia +0.055, 15 archetypes, "knee" (presupuesto), frase del abstract del sanity check, y la cabecera "preregistered observation conditions, sealed with the confirmatory run". Fig. 3 (cualitativa externa) incluida.

**Estado: CERRADO. Main 24 págs (18 tablas, 3 figs) · Suplemento 21 págs (20 tablas S1–S20) · 0 errores / 0 undefined / 0 warnings en ambos.**
