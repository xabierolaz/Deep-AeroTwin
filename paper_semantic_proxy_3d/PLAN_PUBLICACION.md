# Plan de publicacion: SPPA semantic proxy 3D

Titulo actual: `SPPA: A Deterministic Runtime Contract for Semantic Primitive Proxy Actors in UAV Digital Twins`

## Estado

| Campo | Valor |
|---|---|
| Estado | Borrador LaTeX con PDF generado; precheck de contrato runtime aprobado, pero no listo como full experimental paper |
| Archivo principal | `semantic_proxy_3d_paper.tex` |
| Bibliografia | `semantic_proxy_3d_references.bib` |
| Figura disponible | `figures/sppa_proxy_contact_sheet.png` |
| Idea central | Convertir detecciones UAV tipo YOLO en proxies 3D semanticos, ligeros y georreferenciables para geovisualizacion en digital twins. |

## Objetivo de baremo

| Salida | Puntos esperados | Lectura |
|---|---:|---|
| Revista JCR Q1 | Hasta 3 | Objetivo preferente. |
| Revista JCR Q2 | Hasta 2 | Objetivo realista si la evaluacion queda solida. |
| Revista JCR Q3 | Hasta 1 | Aceptable si el tiempo aprieta. |
| Demo/congreso corto | Bajo | Evitar salvo que sea paso intermedio necesario. |

## Movimiento recomendado

Objetivo preferente: `Journal of Geovisualization and Spatial Analysis` si se confirma cupo APC de Springer con BUPNA. El encaje correcto no es "sistema de vuelo" ni "VR teleoperacion", sino representacion/geovisualizacion de detecciones UAV como objetos 3D aproximados dentro de un digital twin.

No enviarlo como demo corta todavia si se puede ampliar. El manuscrito ya tiene una propuesta metodologica clara, pero el abstract reconoce que faltan validaciones empiricas clave. Para que pueda competir como articulo de revista, conviene cerrar primero:

- Benchmark de tiempo por objeto y escalabilidad con escenas densas.
- Comparativa contra alternativas simples: bounding boxes, billboard sprites, asset retrieval fijo, mallas genericas y descriptors compactos.
- Caso UAV/digital-twin o simulador reproducible con metricas de estabilidad visual e interpretacion espacial.
- Tabla de ablation: semantica, escala, fallback, incertidumbre.
- Repositorio o paquete suplementario minimo, si no compromete propiedad intelectual.

## Revistas candidatas a estudiar

| Revista | Encaje | Verificacion pendiente |
|---|---|---|
| Journal of Geovisualization and Spatial Analysis | Mejor encaje: geovisualizacion 3D, UAV, objetos dinamicos, representacion espacial, digital twins | Confirmar cupo APC Springer y JCR/Q1 vigente antes de enviar. |
| Robotics and Autonomous Systems | Plan B si Springer no tiene cupo; encaje por UAV/robots, pero exige validacion mas robotica | Confirmar acuerdo Elsevier y preparar evaluacion mas fuerte. |
| Virtual Reality | Solo si el paper se desplaza otra vez a HMD/interfaz, lo cual debe quedar para Pipeline B | No mezclar con SPPA salvo como integracion futura. |
| Computers & Graphics | Encaje grafico/rendering, pero no es la prioridad si se busca JCR Q1 estricto | Verificar cuartil actual y APC. |
| SoftwareX | Artefacto software reproducible | Buena si se prioriza paquete tecnico sobre impacto alto. |

## Evidencias que debera guardar la subcarpeta

- Hoja JCR/SJR de la revista antes de enviar.
- PDF enviado.
- Confirmacion de envio.
- Cartas de decision/revision.
- Carta de aceptacion.
- DOI y version of record.
- Primera pagina del articulo publicado.

## Siguiente paso concreto

Aplicar `SPPA_PAPER_RESTRUCTURE_PLAN.md`: convertir el suplemento largo en artefacto tecnico, conservar solo la evidencia que sube el nivel del main paper, y cerrar los cuatro gates minimos: benchmark comun, detecciones/crops con referencia, perfilado Unreal por fase, y tasas de scheduler derivadas de logs.

Estado operativo actual: `SUBMISSION_PRECHECK.md` marca el main como viable para
un envio de contrato runtime preliminar, pero bloquea cualquier claim de paper
experimental completo. El suplemento de 38 paginas debe tratarse como artifact
log, no como suplemento formal. La decision queda ahora auditada en
`SUPPLEMENT_TRIAGE.md`: 38 paginas, 2.402 lineas TeX, decision
`do_not_submit_current_38_page_file`, forma preferida
`main_paper_plus_short_artifact_index`.
