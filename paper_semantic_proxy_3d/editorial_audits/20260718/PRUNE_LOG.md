# PRUNE LOG — Poda estructural D4 (agresiva) del paper SPPA-MVFit

**Fecha:** 2026-07-18
**Decisión aplicada:** D-RES / D4 (poda agresiva, main objetivo ~18–22 págs.) + T5 (reencuadre Tabla 6) + T6 (bloat estructural) del `UNIFIED_EXTERNAL_FEEDBACK.md`.
**Documentos:** `semantic_proxy_3d_paper.tex` (main) · `semantic_proxy_3d_submission_supplement.tex` (suplemento).
**Backup pre-poda:** `D:\Deep-AeroTwin-UE57-Test\sppa_audit\backup_pre_prune\` (copia íntegra de ambos .tex antes de cualquier edición).

---

## 1. Métricas antes / después

| Documento | Antes | Después |
|---|---|---|
| Main: líneas tex | 1 642 | 817 |
| Main: páginas PDF | 34 | **16** |
| Main: tablas | 22 | **7** (objetivo ≤8 ✔) |
| Main: figuras | 6 | 2 (sppa-flow, mvfit-h1-examples) |
| Suplemento: líneas tex | 150 | 1 082 |
| Suplemento: páginas PDF | 4 | **19** |
| Suplemento: tablas | 1 | 14 (S1–S14) |
| Suplemento: figuras | 2 (S1–S2) | 6 (S1–S6) |

Compilación final (MiKTeX, `-jobname=sppa_check` / `-jobname=supp_check`, ciclo completo pdflatex → bibtex → pdflatex×2):
- **Main: 0 errores, 0 undefined refs, 0 warnings de LaTeX.**
- **Suplemento: 0 errores, 0 undefined refs/citations, 0 multiply-defined.**

## 2. Mapa final de secciones del main

1. Introduction
2. Contribution and Scope
3. SPPA Contract — 3.1 Part Graph · 3.2 Pose, Yaw, and Updates · 3.3 End-to-End Pipeline (`sec:pipeline`) · 3.4 Descriptor and Runtime Backend (antigua §7 Implementation, rebajada a subsección) · párrafo "Language model use (offline only)" integrado en la intro del contrato
4. Related Work
5. Family-Conditioned SPPA-MVFit (`sec:mvfit`)
6. Primary Results (T2–T5 + Fig. 2)
7. External Neural Comparison (Input-Modality Mismatch) (`sec:neural-external-wave`, T6 + prosa reescrita)
8. Real-Image Probes and Deployment Summary (`sec:deployment-summary`, NUEVA: tabla probes fusionada + tabla runtime reducida + punteros al suplemento)
9. Discussion
10. Threats to Validity (5 amenazas; ítem Holm eliminado)
11. Claim Boundaries (`sec:claim-boundaries`, fuente única de disclaimers)
12. Conclusion

Tablas main: `tab:mvfit-h1`, `tab:mvfit-means`, `tab:mvfit-secondary`, `tab:mvfit-family-strata`, `tab:neural-external-wave`, `tab:real-probe-summary` (nueva fusionada), `tab:deployment-runtime-summary` (nueva reducida).

## 3. Mapa final del suplemento

Front matter (sin numerar): Purpose (actualizado) · Primary endpoint · Reproduction commands (Tabla S1) · Selected sealed hashes · Claim boundaries.

- **S1** Representation Design Space (movida desde §4 del main; Tabla S2 = `tab:representation-design-space`)
- **S2** External Neural Wave: Protocol Details and Exclusions (minucias de la antigua §10.1: selección de casos, calibración 48-candidatos, crashes, exclusiones SF3D/SPAR3D/TRELLIS.2)
- **S3** Verifier-Gated Open-Label Probe (Tabla S3 = T7 solo con filas verifier-gated; + párrafo de perfiles quadruped/open-label movido desde la antigua §3 del main)
- **S4** OBJ Construction Sanity Check (Legacy) (antigua §10.3, verbatim)
- **S5** Benchmark Alignment, Stress Test, and Real-Image Probes (antigua §10.4)
  - S5.1 Substitutability Stress Test (Preliminary, Superseded) — Tabla S4 = T8 con sus notas; Fig. S1 = input-alignment grid
  - S5.2 Real-Image Dual-Input Probes — Fig. S2 = probe grid; Fig. S3 = zoom audit (antigua S1 del suplemento); Tabla S5 = **F1 (T9+T19 fusionadas)**; Tabla S6 = **F2 (T10+T14)**; Tabla S7 = T11; Fig. S4 = mode comparison; Tabla S8 = **F3 (T12+T13)**
  - S5.3 Real-Image Metric Replay and Replay Verifier
  - S5.4 Agnostic Image-Space Primitive Probe and Visual Bridge — Tabla S9 = **F4 (T15+T16)**; Fig. S5 = visual part evidence (antigua S2 del suplemento); Tabla S10 = T17; Tabla S11 = T18; Fig. S6 = agnostic probe
  - S5.5 Controlled Contract Benchmarks — Tabla S12 = T20; Tabla S13 = T21
- **S6** Role-Preservation Diagnostic (antigua §10.5, verbatim)
- **S7** Descriptor and Unreal Runtime Tests (antigua §10.6, verbatim, con timestamps; Tabla S14 = T22)
- Bibliografía propia (`semantic_proxy_3d_references.bib`; necesaria para las 6 claves citadas en el contenido movido).

## 4. Contenido MOVIDO (verbatim salvo cortes aprobados)

| Bloque origen (main pre-poda) | Destino | Notas |
|---|---|---|
| §4 Representation Design Space (252–286) | S1 | No estaba en el esqueleto aprobado de 12 secciones; contenido conservado íntegro en suplemento |
| §10.1 minucias protocolo (694–720) | S2 | verbatim |
| §10.2 open-label probe (777–814) | S3 | con cortes de §5 |
| §10.3 OBJ legacy (815–826) | S4 | verbatim |
| §10.4 stress test + probes + replay + anti-shortcut (827–1306) | S5 | con fusiones y dedup de §5 |
| §10.5 role-preservation (1307–1338) | S6 | verbatim |
| §10.6 descriptor/Unreal (1339–1533) | S7 | verbatim (timestamps conservados) |
| Párrafo quadruped/open-label de §3 (217–241) | S3 | movido, no eliminado: perfiles de morfología quadruped + admisión open-label |

## 5. Contenido ELIMINADO (no movido) — lista exacta

1. **Fila "Before alignment" y fila "After contract alignment"** de T7 (`tab:open-label-probe`, historia de desarrollo del resolver) + frase de progresión asociada. Se conservan las 2 filas verifier-gated (resultados "After" actuales) y la frase que explica las condiciones metric/tag-only (necesaria para leer la tabla).
2. **Frase de victoria de §10.1** ("exceeds ... 0.330–0.433 ... 52×–5,767× fewer ... 41×–208× faster ... ≈3.2×10⁴× smaller", pre-poda 755–759). Sustituida por framing de input-modality mismatch (mini-turbo ≠ flagship, n=60 / oblique n=58 con 2 crashes, no-leaderboard + puntero a §11) + línea que reconcilia 3.09M tris (media top-mask T6) vs 1.7M máx (T8 preliminar superada).
3. **§3 "Language Model Use and Geometry Path" completa (165–251)** salvo lo movido a S3: sustituida por UN párrafo "LLM-assisted offline design; no LLM at runtime" dentro de §3 SPPA Contract. Incluye:
   - Enumeración de 5 pasos del pipeline (191–215): duplicado de `sec:pipeline` → eliminada, cita conservada.
   - Párrafo "honest novelty boundary" (243–250): duplicado del cierre de Related Work (misma lista de áreas maduras + misma claim) → eliminado como duplicado.
4. **Dos cajas rojas** `\textcolor{red}{Claim boundary:...}` (pre-poda 151–153 y 673–675): eliminadas; §11 Claim Boundaries es la fuente única (puntero `\ref{sec:claim-boundaries}` añadido donde procedía).
5. **Disclaimers duplicados en §§2–9** podados a uno por sección + puntero a §11: §2 (prosa de la caja roja), §3 contrato (doble boundary + "implementation guard, not proof"), §3.1 ("not a visual comparison ... not proof"), §3.4 ("not a validated human-factors result"; "not evidence that the ontology is complete").
6. **Ítem 6 de Threats** ("Holm-style secondary p-values ... not used in this manuscript"): eliminado; Threats queda con 5 ítems.
7. **Re-narraciones del pipeline en §10.4** (dedup aprobado): la triple descripción text-only/detector+metric/+visual y la re-narración numérica del worked example tractor-trailer (0.47; 16.85×6.21×3.40 → 12.11×3.76×3.40) se sustituyen EN EL SUPLEMENTO por citas a `sec:pipeline` del main (los números siguen en la Tabla S5 fusionada y en el worked example del main, que es la versión conservada).
8. **Tabla T19 standalone** (`tab:real-image-assumed-flight-replay`): absorbida por la fusión F1 (Tabla S5); su prólogo y el verificador de replay se conservan como prosa (S5.2/S5.3).
9. **Preámbulo de §10 "Secondary Systems Evidence"** (677–681): sustituido por la nueva §8 con su propio disclaimer único + puntero a §11.

## 6. Fusiones de tablas ejecutadas (en suplemento)

- **F1 = T9 + T19** → Tabla S5 (`tab:sppa-observation-fusion-audit`): evidencia YOLOE+conf, proxy replay, dims crudas, dims gateadas, gate, pose local, tris. Nota de caption: la columna "replay proxy" reporta la familia detector-only en tiempo de replay (heavy_vehicle para tractor-trailer, verbatim de T19); las familias refinadas por observación están en Tabla S6 — evita fabricar consistencia entre dos filas verbatim que difieren.
- **F2 = T10 + T14** → Tabla S6 (`tab:real-probe-normalization`): familias detector-only / detector+observación / texto revisado + regla, ms y tris del refinamiento.
- **F3 = T12 + T13** → Tabla S8 (`tab:sppa-input-mode-comparison`): ablación input-mode con columna Ch. de canales y wall time.
- **F4 = T15 + T16** → Tabla S9 (`tab:sppa-visual-part-evidence`): cues, roles, visual tris, ms, tris + ejes visual/footprint yaw, Δ y acuerdo.
- T8 (S4), T11 (S7), T17 (S10), T18 (S11), T20 (S12), T21 (S13), T22 (S14): movidas sin fusionar (T11/T17/T18 vía `\input` a los .tex generados, intactos).
- **Nuevas en main:** `tab:real-probe-summary` (4 probes: familia, confianza YOLOE, dims cruda→gateada, tris, wall ms — columnas pedidas; no existe IoU por ausencia de GT 3D, declarado en caption) y `tab:deployment-runtime-summary` (P50/P95 clave descriptor/update/scheduler + replay empaquetado 100 obj + HISM 500 obj parcial; SIN timestamps).

## 7. Cross-referencias

- **Main → suplemento:** texto literal (mecanismo preexistente): "Supplementary Section S.2/S.3/S.5/S.6", "Supplementary Sections S.3–S.7", "Supplementary Table S.5/S.14", "Supplementary Figure S1/S3". Verificado contra `supp_check.aux`: S5 = tabla obs+replay fusionada ✔, S14 = unreal-selected ✔, S1 fig = alignment grid ✔, S3 fig = zoom audit ✔.
- **Suplemento → main:** `xr-hyper` + `\externaldocument[main-]{sppa_check}` (el prefijo evita colisión de bibcite entre las dos bibliografías). `\ref{main-sec:pipeline}` → 3.3 ✔; `\ref{main-sec:neural-external-wave}` → 7 ✔. Todas las menciones van calificadas con "of the main paper".
- **Labels movidos** conservan su nombre (sin colisiones; el main ya no los define). Labels absorbidos por fusiones (`tab:real-image-assumed-flight-replay`, `tab:sppa-detector-observation-refinement`, `tab:sppa-evidence-channel-coverage`, `tab:sppa-visual-metric-yaw`) redirigidos en prosa a la tabla fusionada correspondiente.
- **Renumeración de figuras del suplemento** (por orden de aparición tras integrar las movidas): antigua S1 (zoom audit) → **S3**; antigua S2 (visual part evidence) → **S5**; alignment grid → S1; probe grid → S2; mode comparison → S4; agnostic → S6. Las dos referencias literales del main se actualizaron en consecuencia.
- Suplemento ya no cita figuras del main como "Supplementary Figure Sx": usa `\ref` internos (`fig:supp-zoom-audit`, `fig:supp-visual-part-evidence`, labels movidos).
- **Cross-refs no resueltos: ninguno** (0 undefined en ambos documentos).

## 8. Otros cambios aprobados aplicados

- **Abstract:** tras 9.4 ms añadido "(fitter wall time; the packaged Unreal runtime is characterized separately in the supplement)".
- **§7 Implementation** → subsección 3.4 "Descriptor and Runtime Backend" (`sec:implementation`); contenido conservado salvo los dos disclaimers duplicados.
- **Related Work:** la figura comparativa ahora apunta a "Supplementary Figure S1".
- **Título del suplemento** actualizado ("...Claim Boundaries, and Secondary Systems Evidence") + sección Purpose actualizada (ya no es "short supplement").

## 9. Decisiones editoriales tomadas (documentadas para revisión)

1. **"After contract alignment" también eliminada** (además de "Before alignment"): ambas son historia de desarrollo (auditoría §5 recomienda recortar ambas; la decisión del usuario dice "conserva solo resultados 'After'"). Las filas verifier-gated son los resultados actuales.
2. **§4 Representation Design Space movida a S1** en vez de eliminada: el esqueleto aprobado de 12 secciones no la incluye, pero la regla 1 prohíbe perder contenido; la referencia desde S6 (role-preservation) queda interna al suplemento.
3. **Dedup de figuras de probes resuelto a nivel de documento:** la duplicidad señalada era main-vs-suplemento (auditoría E.4: "duplicidad main/suplemento"). Tras el movimiento, los 4 probes solo aparecen en el suplemento. Las 4 figuras se conservan porque cada una muestra una capa de evidencia distinta (grid comparativo multi-método, zoom de evidencia detector, ablación 3-modos, cues visuales); ninguna es duplicado de otra. El main no retiene figura de probes (solo tablas en §8).
4. **Párrafo quadruped/open-label (217–241) movido a S3** en lugar de eliminado con §3 (contiene números únicos: 836–1180 triángulos, 0.61 ms, perfiles de morfología).
5. **Reorden local dentro de S5:** el verificador de replay (antes tras la antigua T19) se colocó junto a la prosa de replay (S5.3); subsecciones S5.1–S5.5 añadidas para resolver el "heading trampilla" (auditoría E.1).
6. **No tocado:** `reproducibility\sppa_mvfit\`, `supporting_artifacts\`, `benchmarks\results\*.tex` (los .tex generados se referencian, no se modifican), `.bib`, figuras. Sin git commit.

## 10. Verificación de compilación (cierre)

```
main:  pdflatex -jobname=sppa_check → bibtex sppa_check → pdflatex ×2
       Output written on sppa_check.pdf (16 pages). 0 errores, 0 undefined, 0 warnings.
supp:  pdflatex -jobname=supp_check → bibtex supp_check → pdflatex ×2
       Output written on supp_check.pdf (19 pages). 0 errores, 0 undefined, 0 warnings.
```

Nota operativa: el suplemento debe compilarse DESPUÉS del main (xr lee `sppa_check.aux`).
