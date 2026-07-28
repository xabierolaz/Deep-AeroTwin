# PORCE / Unreal - Estado base tras importar `porce_last`

Fecha: 2026-06-16

## Fuente viva del paper

La unica fuente de paper que debe usarse a partir de ahora es:

- `papers/porce_collision_evasion/Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion/`

Esa carpeta se ha reconstruido desde `porce_last.zip`. El zip original queda guardado como referencia en:

- `paper/_source_archives/porce_last.zip`

No trabajar sobre los exports antiguos ni sobre las versiones previas archivadas salvo para recuperar contexto.

## Historico

Todo el material anterior de paper, docs, capturas, PDFs y temporales de trabajo se ha movido a:

- `historico/2026-06-16_porce_pre_porce_last/`

Contenido principal:

- `paper/`: antigua carpeta completa del paper antes de `porce_last`.
- `raiz/docs/`: documentacion anterior, auditorias y borradores.
- `raiz/tmp/`: temporales, pruebas, scripts auxiliares y artefactos generados.
- `raiz/*.pdf`, `raiz/*.zip`, capturas y handoffs antiguos.
- `porce_last_extracted_manifest.csv`: manifiesto de los 24 ficheros extraidos del zip nuevo.

## Verificacion de importacion

- `porce_last.zip` contiene 24 ficheros y no falta ninguno en la extraccion viva.
- La carpeta viva contiene esos 24 ficheros mas productos generados por compilacion.
- Producto compilado disponible: `papers/porce_collision_evasion/Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion/Main_formato_ieee.pdf`.
- Producto generado por LaTeX: `IEEE/TII-Articles-LaTeX-template/TII-eps-converted-to.pdf`.
- La compilacion no muestra errores fatales. Avisos no bloqueantes detectados: clase `ieeecolor`, una etiqueta duplicada (`deteccion dentro del margen`) y ajustes automaticos de floats `!h` a `!ht`.
- En raiz ya no quedan ZIP/PDF/PNG antiguos del paper; estan en historico.
- `operacion/`: bitacoras `GIT_STATUS*.txt` generadas durante la reorganizacion y verificacion.

## EASA preservado en raiz

La version nueva de Overleaf no trae los artefactos especificos de operacionalizacion EASA que habiamos preparado. Se han preservado en raiz:

- `EASA_TRAZABILIDAD_PORCE.tex`: texto y tablas paste-ready para conectar EASA/SORA con mecanismo de algoritmo y artefactos de repo.
- `EASA_FORMULACION_SEGURIDAD_PORCE.tex`: formulacion matematica con `R_s(clase)`, Ground Risk Buffer 1:1, inflado por obstaculo y condicion reactiva de seguridad.
- `EASA_REFERENCIAS_PORCE.bib`: referencias regulatorias minimas para reinsertar en el paper.

## Puntos importantes para el proyecto Unreal

- El peso tecnico fuerte del proyecto no es solo "evitar obstaculos", sino el loop auditable: deteccion -> Brain -> A* local -> MAVLink/Unreal -> logs.
- La contribucion EASA defendible esta en hacer que la seguridad dependa de la clase del obstaculo: persona/biker con radio derivado de SORA, animal y torre con radios distintos, unknown como caso conservador.
- Si el nuevo Overleaf se mantiene como base, hay que reinsertar la trazabilidad EASA y armonizar el texto con el codigo: `R_s(clase)`, no un radio unico de 12 m.
- Para resultados nuevos, no reutilizar numeros antiguos sin reejecutar: cambiar el radio persona 12 m -> aprox. altura operativa altera trayectoria, separacion minima, detour y metricas.
- Mantener claro que el metodo es reactivo: no predice trayectoria del obstaculo. Se defiende con latencia, margen, condicion de deteccion y auditabilidad, no como politica black-box.
- Para Unreal, conviene que cualquier demo o captura que alimente el paper salga de la fuente nueva y de ejecuciones reproducibles, no de temporales del historico.
