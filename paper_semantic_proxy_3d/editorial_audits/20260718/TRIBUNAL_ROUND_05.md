# TRIBUNAL ROUND 05 — 2026-07-18 (post-reestructuración mayor)

**Objeto:** versión tras poda 34→24 págs + integración de 12 piezas de evidencia nueva (Fases A–C del feedback externo unificado, `UNIFIED_EXTERNAL_FEEDBACK.md`).
**Método:** tribunal de 4 voces (editor Q1 aplicado, metodólogo, revisor CV/3D escéptico, ingeniero de sistemas) con verificación bit a bit de 24 números contra fuentes selladas/artefactos.

## Veredicto: ACCEPT con MINOR ISSUES (4/4)

| Voz | Veredicto | Motivo |
|---|---|---|
| Editor Q1 aplicado | ACCEPT | Reestructuración acertada; §8 ejemplarmente honesto |
| Metodólogo | MINOR ISSUES | 3 deslices numéricos/verbales (H1, H2, H5) |
| Revisor CV/3D escéptico | MINOR ISSUES | framing §8 selectivo sobre primitivas triviales (H8); 2 frases literalmente falsas (H3, H4) |
| Ingeniero de sistemas | ACCEPT | poda íntegra, 0 refs rotas; 2 higiene (H6, H7) |

## Verificación numérica: 20/24 OK, 4 KO menores (ninguno toca la ciencia sellada)

## Hallazgos H1–H8 y su resolución (TODOS aplicados 2026-07-18, mismo día)

- **H1** "statistically indistinguishable" OBB vs AABB con IC excluyendo 0 → reescrito: "practically identical; paired Δ −0.004 CI [−0.005,−0.003] — statistically detectable but an order of magnitude below the +0.030 margin". ✅
- **H2** barrido 61−31 mal redondeado (+0.003 [−0.001,+0.006]) → +0.002 [−0.001,+0.005] en main y caption S.19. ✅
- **H3** rango espesores lattice 0.09–0.23 → 0.09–0.37 (placas 0.09–0.18). ✅
- **H4** "all eight methods ≤0.24" falso (hull 0.431) → "the seven actor methods ≤0.24 (visual hull at most 0.43)". ✅
- **H5** dos medianas para el mismo 31 sellado (9.4 vs 12.6 ms) → nota añadida: sweep = re-run post-hoc, IoU bit-exact. ✅
- **H6** claim boundaries del suplemento sin frontera externa → añadida ("not replicated at n=52"). ✅
- **H7** sección S.1 huérfana → referenciada desde §7 (OBB/design space). ✅
- **H8** §8 callaba que cápsula/elipsoide/AABB ≥ SPPA externamente → frase añadida con los 4 números. ✅

## Estado tras fixes

- Main 24 págs, 0 errores, 0 refs indefinidas. Suplemento 21 págs, ídem.
- Puerta `reproduce_sppa_mvfit_paper.py --strict` → 0 blockers, H1 pass.
- Clean-clone gate: falla SOLO por los 3 ficheros editados sin commitear (paper.tex, references.bib, submission_supplement.tex) → pasa con el commit.

## 5 riesgos residuales (aceptados conscientemente)

1. Evidencia externa honesta y visible: margen no transferido (+0.043 n.s.), primitivas triviales ≥ SPPA en mallas reales → la contribución de ocupación descansa en la distribución de diseño; mitigado con framing (§8, §13, abstract).
2. Brecha de adquisición: la vista side del benchmark no existe en nadir puro; cuantificado con ablación top-only (0.458) y discusión explícita.
3. Autoría compartida de grafos: acotado con 3 variantes pre-registradas (todas peores); solo lo cerraría un baseline externo ejecutado (future work).
4. Racimo de deslices numéricos → corregido en H1–H8 (era el riesgo inmediato).
5. Fallback familia-errónea afirmado, no medido → acotable en texto si un revisor lo pide.
