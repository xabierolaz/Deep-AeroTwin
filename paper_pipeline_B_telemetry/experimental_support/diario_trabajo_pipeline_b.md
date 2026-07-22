# Diario de trabajo - Pipeline B / VRIH

Este archivo es nuestra memoria interna. No forma parte del paper.

La regla desde ahora es sencilla: el paper debe sonar como articulo cientifico, no como agenda de trabajo. Si algo falta, en el paper dejamos una nota roja muy breve, por ejemplo `[PENDIENTE: geospatial validation evidence]`. La explicacion larga de que tenemos que hacer va aqui.

## Donde esta cada cosa

- El paper vivo esta en `pipeline_b_concept.tex`.
- El PDF compilado esta en `pipeline_b_concept.pdf`.
- Esta memoria es el unico `.md` de trabajo. No queremos otro Markdown paralelo porque luego aparecen contradicciones.
- Los scripts, schemas, replay y resultados de apoyo estan en `experimental_support/`.

## Estado general

Tenemos un manuscrito ya pasado a plantilla LaTeX de VRIH. Compila con XeLaTeX y esta orientado como paper de VR/digital twin para operador UAV, no como paper puro de drones ni como paper puro de telemetria.

VRIH ya nos animo a enviar el manuscrito completo despues de leer los preliminary details. Eso solo confirma que el tema encaja en scope; no es aceptacion ni revision cientifica.

El paper ahora defiende una idea acotada: usamos Unreal/Cesium como prior geoespacial y anadimos semantic deltas de sensores/detecciones para reconstruir una escena visible en visor VR. No decimos que sustituya al video, ni que sea interfaz principal de pilotaje, ni que garantice seguridad, ni que sea detect-and-avoid certificado.

## Lo que no debe estar dentro del paper

No debemos meter en el paper frases tipo "debemos grabar", "aqui falta", "Jesus tiene que revisar" o listas largas de tareas. Eso va aqui.

En el paper solo deben quedar tres tipos de cosas:

- Texto cientifico definitivo.
- Resultados, tablas y figuras reales cuando los tengamos.
- Marcadores rojos muy breves mientras falte evidencia.

Cuando sustituyamos un marcador rojo por evidencia real, debemos venir aqui y borrar o actualizar la tarea correspondiente.

## Que significan los pendientes rojos del paper

- `bandwidth evidence`: tenemos que comparar el bitrate de la telemetria semantica contra video H.264/H.265/WebRTC o FPV en el mismo intervalo. Si los tiles de Cesium viajan por el mismo enlace, tambien hay que contarlos.
- `geospatial validation evidence`: tenemos que comprobar que la posicion estimada de los objetos es correcta dentro de la incertidumbre declarada. Necesitamos calibracion, telemetria, pose, terreno y alguna referencia tipo RTK/GNSS, topografia, motion capture o equivalente.
- `geospatial-prior audit`: tenemos que documentar de donde sale el mapa/Cesium/tiles, fecha, cobertura, cache, origen geografico, trafico de tiles y zonas no observadas.
- `sensor/detector configuration evidence`: tenemos que dejar claro que detector o sensor usamos, con version, pesos, clases, umbral, resolucion y condiciones.
- `end-to-end latency evidence`: tenemos que medir desde deteccion/evento fuente hasta actor visible en el visor VR. Debe incluir fuente, Brain, Unreal y visor o mirror.
- `tracking persistence evidence`: tenemos que medir ID switches, fragmentacion, stale duration y despawn con logs reales o replay etiquetado.
- `network degradation evidence`: tenemos que ensayar perdida de paquetes, jitter e interrupciones, y demostrar que lo viejo no aparece como fresco.
- `network degradation and tracking evidence`: tenemos que combinar red degradada con persistencia de actores para ver si el operador recibe estados stale o asociaciones dudosas.
- `Unreal/VR demonstration evidence`: tenemos que grabar Unreal funcionando con Cesium, Brain, actores semanticos y visor VR o mirror de pantalla. No vale solo una figura conceptual.
- `VR-headset figure evidence`: tenemos que sacar una captura real desde el visor VR o mirror de Unreal donde se vea terreno, UAV, actor, etiqueta, confianza, edad/stale e incertidumbre.
- `operator study evidence`: tenemos que probar utilidad con operadores o pilotos, comparando contra video-only, prior-only, sensor/raw o hibrido no inmersivo. No podemos asumir que la escena bonita ayuda.
- `statistical analysis plan`: tenemos que cerrar endpoints, muestra, contrabalanceo, modelo estadistico, exclusiones y comparaciones antes de medir.
- `low-visibility sensor evidence`: tenemos que probar noche, niebla, humo, glare o condiciones equivalentes, separando rendimiento del sensor y legibilidad del render en Unreal/VR.
- `geospatial-prior and low-visibility evidence`: tenemos que demostrar que el prior ayuda cuando falla el video, pero sin sugerir que el prior prueba espacio libre.
- `geospatial-prior validation evidence`: tenemos que comprobar que el prior aporta contexto util y no falsa seguridad frente a prior-only o video degradado.
- `prior-plus-delta utility evidence`: tenemos que demostrar que prior+deltas aporta mas que solo mapa o solo video en la tarea elegida.
- `information-role display taxonomy`: tenemos que cerrar como se distinguen visualmente mapa, observacion viva, delta, inferido, stale, invalido y zona no observada.
- `operational safety envelope`: tenemos que fijar stale maximo, incertidumbre maxima, confianza minima, fallback y limites de uso.
- `reproducibility package`: tenemos que congelar codigo, schemas, logs, fixtures, versiones, commit y README de reproduccion.
- `reproducibility and safety evidence`: tenemos que dejar el paquete revisable junto con umbrales y logs que permitan auditar el comportamiento.
- `measured evaluation results`: tenemos que sustituir los pendientes por resultados reales antes de una version limpia de envio.
- `funding and acknowledgements`: tenemos que completar financiacion, proyectos, ayudas y agradecimientos.
- `CRediT author roles`: tenemos que cerrar contribuciones de Xabier, Daniel, Iker y Jesus, y confirmar autor de correspondencia.
- `competing interests statement`: tenemos que declarar conflictos de interes o ausencia de ellos.
- `data and code availability`: tenemos que decidir que datos/codigo se pueden compartir y que restricciones hay.
- `ethics approval`: tenemos que cerrar aprobacion o exencion etica si hacemos estudio con operadores.
- `AI-use declaration`: tenemos que declarar uso de IA segun VRIH/Elsevier si aplica.

## Que tenemos ya avanzado

Tenemos el framing VRIH, abstract, related work, metodo formal, ecuaciones de georreferenciacion, modelo de incertidumbre, latencia, ancho de banda, stale/despawn, limitaciones y safety envelope.

Tenemos 51 referencias en el manuscrito. Las referencias con DOI se auditaron y resuelven. La bibliografia esta inline con `thebibliography`, como en la plantilla VRIH; no necesitamos `.bib` salvo que queramos gestionarlo aparte y luego aplanarlo.

Tenemos soporte software-only en `experimental_support/`: schemas, replay determinista, outputs de validacion de contrato, benchmark sintetico de ancho de banda, simulacion de red, tracking sintetico y borradores de protocolos. Eso ayuda, pero no sustituye evidencia real de vuelo, visor VR, georreferenciacion o usuarios.

El PDF queda ahora en 21 paginas despues de sacar del paper la guia interna de pendientes. Es una mejora: el manuscrito parece mas articulo y menos memoria de proyecto.

## Que requiere evidencia fisica o instrumentada

Tenemos que conseguir una demo real de Unreal/VR con visor o mirror. Esa es la pieza visual clave para VRIH.

Tenemos que usar videos de vuelo con telemetria que ya solemos guardar, o preparar HITL con ArduPilot/autopiloto, o hacer vuelo real. Si usamos replay, lo diremos como replay. Si usamos HITL, lo diremos como HITL. No debemos mezclar niveles de evidencia.

Tenemos que medir latencia real de fuente a visor VR. Los tiempos software-only no bastan para el claim completo.

Tenemos que validar georreferenciacion con calibracion y ground truth. Si no podemos, hay que rebajar el claim de posicionamiento.

Tenemos que comparar contra video. En condiciones optimas, video puede ser mejor. Nuestro caso fuerte es enlace degradado, poca visibilidad, campo de vision insuficiente, necesidad de reducir ancho de banda, o sensor crudo dificil de interpretar que se vuelve legible al reconstruirse en Unreal/VR.

Tenemos que probar baja visibilidad de forma honesta. Unreal puede renderizar claro, pero eso solo vale si el sensor realmente observo algo o si marcamos claramente lo que viene del prior, lo que esta stale y lo que no ha sido observado.

Tenemos que decidir si hacemos estudio con operadores. Si lo hacemos, necesitamos protocolo, etica, baselines, workload, awareness, confianza y sickness.

## Orden recomendado desde aqui

1. Sacamos captura/video real de Unreal/VR con visor o mirror y logs asociados.
2. Elegimos la fuente experimental principal: replay de videos de vuelo con telemetria, HITL, vuelo real o combinacion.
3. Medimos ancho de banda contra video en el mismo tramo.
4. Medimos latencia fuente--Brain--Unreal--visor VR.
5. Validamos georreferenciacion con calibracion y referencia externa.
6. Ensayamos perdida/jitter/stale y tracking.
7. Probamos baja visibilidad con RGB degradado o sensor alternativo.
8. Cerramos safety envelope y reproducibility package.
9. Si procede, ejecutamos estudio con operadores.
10. Eliminamos todos los rojos del paper o los convertimos en resultados/limitaciones antes de enviar.

## Regla final

El paper debe quedar limpio y defendible. Esta memoria puede ser practica, imperfecta y directa. Si una frase suena a "nota para nosotros", debe vivir aqui, no en el manuscrito.

## Auditoria canonica del 15-07-2026

### Dictamen de entrada

- El paquete no esta listo para envio. El `.tex` contiene 78 llamadas a `\pendiente{...}` y no hay una seccion de resultados experimentales.
- El fit tematico con VRIH es fuerte y la invitacion del 01-07-2026 confirma solamente el scope preliminar.
- El riesgo de desk reject es practicamente seguro si se envia como Research Paper sin resultados, porque la guia oficial exige experimentos o ensayos, resultados innovadores y conclusiones.
- El repositorio operativo contiene mas implementacion y evidencia software de la reflejada en el paper, pero no contiene todavia una demostracion HMD/VR trazable ni resultados humanos, geoespaciales o source-to-photon.

### Requisitos oficiales VRIH verificados el 15-07-2026

Fuente oficial: `https://www.sciencedirect.com/journal/virtual-reality-and-intelligent-hardware/publish/guide-for-authors`.

| Requisito | Estado | Accion |
|---|---|---|
| Tipo editorial | Research Paper | Mantener; no existe una categoria ordinaria de protocol/concept paper que resuelva la ausencia de resultados. |
| Fuente editable | Parcial | Entregar `.tex`, clase, figuras separadas y PDF de control. El PDF solo no es fuente aceptable. |
| Abstract <=250 palabras | Formalmente cumple: 201 palabras | Reescribir al final para incluir resultados y conclusion empirica. |
| Keywords | Cumple: 7 | Revisar que no haya expresiones innecesariamente largas. |
| Highlights | Existe archivo separado | Reescribir: `HMD trials compare...` es prospectivo y hoy resulta engañoso. Deben ser 3--5 bullets, maximo 85 caracteres cada uno. |
| Figuras separadas | Parcial | Usar PDF/EPS vectorial para diagramas y PNG/JPG/TIFF con resolucion oficial para capturas/fotos. |
| Imagenes generadas por IA | Prohibidas para el envio | No generar ni incluir artwork, graphical abstract o figuras AI-generated, aunque se etiqueten como conceptuales. |
| Suplementos y video | Pendiente | Citar cada archivo en el manuscrito; maximo preferido 150 MB por video y 1 GB total; incluir still y descripcion accesible. |
| Corresponding author | Parcial | Jesus aparece con email. Faltan direccion postal completa, telefono para Editorial Manager y confirmacion de correspondencia. |
| Competing interests | Pendiente de autores | Ademas del texto del paper, generar con la herramienta Elsevier el `.doc/.docx` obligatorio. |
| Funding | Pendiente de autores | Declarar financiacion y papel del financiador, o la frase oficial de ausencia de grant. |
| CRediT | Pendiente de autores | Requiere aprobacion de los cuatro autores antes del envio. |
| AI-use declaration | Pendiente de autores | Declarar nombre de herramienta, uso para escritura, revision humana y responsabilidad; no declarar figuras AI porque no se permiten. |
| Ethics | Bloqueado si hay estudio humano | Obtener aprobacion o exencion antes de recoger datos. No se puede resolver retroactivamente. |
| Data/code | Parcial | Congelar commit, versiones, schemas, fixtures, logs y condiciones de acceso/deposito. |
| Referencias | Parcial | Corregir DroneVR 257--262, AirSim y auditar referencias nuevas/recientes y software. |
| APC | Informativo para autores | USD 1200 mas impuestos para envios desde 01-01-2026; confirmar conocimiento de todos los autores. |

### Matriz de preparacion para envio

| Bloque | Estado al 15-07-2026 | Evidencia existente | Bloqueo o siguiente accion |
|---|---|---|---|
| Scope/invitacion | Listo | `vrih_scope_encouragement_2026-07-01.txt` | No presentarlo como aceptacion. |
| Plantilla | Parcial | `VRIH2025.cls`, `.tex`, PDF de 21 paginas | Recompilar y revisar campos editoriales vacios. |
| Novedad | En revision | Contrato/runtime y prior mas estado semantico | Posicionar frente a synthetic/hybrid vision, HoloGCS, AeroAssistant y YOLOTransfer-DT. |
| Runtime POST--Brain--GET--Unreal | Software verificado parcialmente | Codigo real, build UE 5.7 y `E2E_ZERO_TRUST_AUDIT.json` del 01-07-2026 | Congelar commit y ejecutar replay trazable con logs del actor visible. |
| Freshness/stale/provenance/uncertainty | Bloqueo fatal de implementacion | Brain publica `track_age_s` pero Unreal no lo consume | Implementar timestamp de fuente, secuencia, clock domain, rechazo out-of-order, stale visual y remove; evitar que polling rejuvenezca tracks. |
| Semantic delta | Claim sobredimensionado | GET devuelve snapshots completos a 5 Hz | Renombrar como semantic object-state snapshots o implementar create/update/delete/tombstones/diff real. |
| Georreferenciacion | Codigo plausible, no validado | `pipeline/geo_projector.py` y ecuaciones del paper | Alinear clamp flag, intrinsics, distortion, timestamp, datum/altitud, terreno y ground truth. |
| Unreal/Cesium | Parcial | Plugin, assets y capturas editoriales antiguas | Las capturas actuales no tienen trazabilidad HMD ni HUD de provenance/freshness; no usarlas como evidencia experimental principal. |
| HMD/OpenXR | No demostrado | Ninguna captura HMD/mirror trazable | Ejecutar runtime real con dispositivo, version, refresh, tracking, frame timing, mirror y logs. |
| Bandwidth | Solo fixture sintetico | JSON/replay y tamaños de payload | Medir bytes on-wire/PCAP, headers, retries, pose, GET, C2 y tiles en mismo intervalo que video real. |
| Loss/jitter/outage | Simulacion defectuosa | Script de benchmark actual | Reescribir con cola de llegada, reordenamiento y modelo de transporte; luego ejecutar red realista pareada. |
| Latencia | Solo presupuesto sintetico | Componentes simulados | Corregir origen temporal de la ecuacion y medir source-to-visible/source-to-photon. |
| Tracking | Parcial | Brain EMA/TTL y replay sintetico | Evitar confianza maxima pegajosa, definir identidad, medir ID switches, fragmentacion y lag. |
| Safety envelope | No cerrado | Lista de variables | Definir ODD y umbrales preespecificados; defaults software no equivalen a limites de seguridad. |
| Low visibility | No ejecutado | Discusion y referencias | Elegir una configuracion sensorial concreta; separar observabilidad del sensor de legibilidad del render. |
| Estudio humano | No ejecutado | Protocolo y SAP preliminares | Si se conserva beneficio humano: etica previa, diseño factorial, endpoint primario, muestra, contrabalanceo y baselines pareados. |
| Figuras | Una arquitectura | PDF/SVG/PNG de arquitectura y capturas Unreal no trazables | Corregir flechas que sugieren control HMD; añadir solo capturas reales y graficos derivados de datos. |
| Declaraciones | Abiertas | Placeholders en el `.tex` | Requieren confirmacion humana: funding, CRediT, conflictos, disponibilidad, etica y AI use. |
| Paquete Editorial Manager | Incompleto | Highlights preliminares e invitacion | Preparar cover letter, declaraciones `.docx`, lista de archivos, captions/supplement/video y metadatos. No enviar sin autorizacion. |

### Hallazgo critico de falsa frescura

La auditoria del codigo real encontro que el contrato descrito en el paper no existe todavia de extremo a extremo:

1. `POST /api/obstacles` no conserva como contrato operativo el tiempo de captura, secuencia, clock domain, incertidumbre o information role.
2. Brain calcula `track_age_s` desde la recepcion y conserva la confianza maxima historica.
3. Unreal no consume `track_age_s`; cada snapshot de `GET /api/ui/data` reinicia `LastSeenTs`.
4. `PruneStaleEntities` elimina al vencer `DespawnAfterS`, pero no existe un estado stale visual.
5. Un track antiguo puede aparecer fresco durante el TTL de Brain y persistir despues en Unreal. Un paquete retrasado puede rejuvenecerlo.

Este defecto debe resolverse en runtime, schemas, tests y texto antes de defender que el sistema evita falsa frescura.

### Evidencia real localizada pero aun no promovida al paper

- `D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260701_144043\E2E_ZERO_TRUST_AUDIT.json`: preflight, build UE 5.7 y pruebas software de REAL_TWIN/SIMULATION. Es evidencia software, no HMD ni flight evidence.
- `D:\Deep-AeroTwin-UE57-Test\Unreal\Saved\Screenshots\precheck_v0.png`, `precheck_v1.png`, `precheck_v2.png` y `precheck_ciclista_v0.png`: capturas reales de Unreal/Cesium con actores, pero sin log vinculado, UI de freshness/provenance, HMD/mirror ni prueba de origen sensorial. Solo candidatas a ilustrar prototipo tras auditar procedencia.
- El README operativo llama a Unreal `interfaz principal`; para este paper y su safety framing debe documentarse como display auxiliar/supervisorio. Esa diferencia no se puede resolver ocultandola: hay que alinear runtime, documentacion y tareas experimentales.

### Primera ronda externa

- Editor-in-Chief simulado: desk reject casi seguro; fit fuerte; falta Results; claims `implemented/evaluated` contradicen la evidencia pendiente.
- Methodologist: bloqueo fatal por falsa frescura, ecuaciones de bandwidth/latency ambiguas, baselines no causales y benchmark de red incorrecto.
- Domain Expert/Competitor: novelty vulnerable frente a synthetic/hybrid vision; `semantic delta` no coincide con snapshots; VR/HMD no esta demostrado.
- Meta-Reviewer: `Reject / not ready for submission`. Confirma que el paquete actual es un documento de diseno y protocolo, no un Research Paper con resultados; eleva a bloqueos fatales la ausencia de resultados, la falsa frescura del runtime y la falta de estudio humano para la pregunta cientifica vigente.

Consenso 4/4: no enviar ni describir como listo. El orden obligatorio es (1) corregir el contrato runtime y congelar una release reproducible, (2) validar tecnicamente HMD, latencia, trafico, georreferenciacion y degradacion, (3) ejecutar el estudio humano solo tras etica y SAP si se mantiene el claim de beneficio al operador, y (4) reescribir como articulo de resultados. La invitacion editorial no cambia este dictamen.
