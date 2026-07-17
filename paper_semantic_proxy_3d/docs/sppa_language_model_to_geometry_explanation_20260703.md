# SPPA: modelo de lenguaje y paso de texto a geometria 3D

Estado: 2026-07-03.

## Respuesta corta

El sistema SPPA actual no usa un modelo de lenguaje en runtime. La ruta de
ejecucion que genera geometria 3D es determinista: etiqueta o deteccion,
normalizador semantico SPPA, receta/arquetipo revisado, primitivas 3D, y actor
en Unreal.

Por tanto, no ocurre esto:

```text
"cow" -> preguntar a un LLM "es mamifero?", "cuantas patas tiene?",
"que piezas tiene?" -> generar geometria nueva en vivo
```

Lo que ocurre es esto:

```text
"cow" o deteccion equivalente
  -> SPPA normalizer
  -> runtime_label/archetype revisado, por ejemplo quadruped/cow
  -> receta revisada: torso + cabeza + patas + material roles
  -> generador determinista: box/ellipsoid/cylinder/sphere/cone/torus
  -> descriptor SPPA-DESC-0.2
  -> backend Unreal crea o actualiza componentes primitivos
```

La unica participacion aceptada de un LLM es offline, como asistente de
autoria. Puede proponer una candidata de receta, pero esa propuesta no entra en
runtime hasta que queda revisada, versionada y cubierta por regresion. El
archivo de recetas declara explicitamente `runtime_llm_allowed: false`, y el
contrato emitido por el resolver declara `runtime_llm_used: false`.

## Que modelo de lenguaje usamos exactamente?

Respuesta honesta: ninguno en runtime.

Los artefactos actuales tampoco registran un nombre de modelo concreto para la
autoria offline. El fichero de candidatos solo distingue fuentes como
`human_reviewed` y `llm_assisted_candidate_reviewed_offline`; no contiene un
campo tipo `model_name`, `model_version`, `prompt_hash` o `provider`.

Por eso el paper no debe afirmar que "usamos GPT-X", "usamos Claude", "usamos
Mistral" o similar. Lo defendible es:

- Runtime: sin LLM, sin API externa, sin razonamiento generativo vivo.
- Offline: posible asistencia LLM para proponer recetas candidatas.
- Gate: revision humana/tecnica, receta versionada, test de resolver, fallback
  para etiquetas no mapeadas.
- Trazabilidad pendiente si queremos reclamar un LLM offline concreto: registrar
  modelo, fecha, prompt, salida, decision de revision y hash de receta.

## Dos entradas distintas: deteccion real vs tag/texto

SPPA tiene que distinguir dos casos porque no aportan la misma evidencia.

| Entrada | Evidencia disponible | Que puede hacer SPPA |
| --- | --- | --- |
| Deteccion real de YOLO/YOLOE | label, confianza, bbox, posible mask/crop, pose o escala externa | Normaliza la etiqueta, usa bbox/mask como evidencia de orientacion o dimensiones si hay calibracion, y genera/actualiza proxy |
| Tag o texto sin imagen | solo una palabra o frase, por ejemplo `truck`, `cow`, `electric pylon` | Selecciona receta revisada y dimensiones por defecto; no puede inferir pose, escala real ni silueta desde imagen |

Esto es importante para las figuras y la evaluacion. Un input de texto no debe
mostrarse como si tuviera la misma evidencia que una imagen detectada. El texto
solo activa una receta. La imagen detectada puede aportar bbox, mask, yaw axial,
color observado y, si hay calibracion, dimensiones.

## Ruta exacta de runtime

1. Un detector o una fuente de texto entrega una etiqueta candidata.
2. `pipeline/sppa_semantic_normalizer.py` convierte etiquetas ruidosas en tags
   SPPA, por ejemplo:
   - `electric pylon` -> `vertical_structure` o `power_tower`
   - `agricultural vehicle` -> `farm_vehicle`
   - `vehicle` -> `generic_vehicle` / familia conservadora
   - `cyclist` y combinaciones persona+bici -> `two_wheeled_rider`
3. `XYT-xabi-yolo-telemetry/xyt_generate_3d.py` llama a `resolve_builder`.
4. `resolve_builder` intenta:
   - match exacto de clase revisada,
   - match por keywords de arquetipo revisado,
   - fallback `unknown` si hay etiqueta vacia, artefacto visual, equipo no
     persona, o etiqueta no cubierta.
5. Si hay dimensiones metricas, mask calibrada o escala externa, se usa
   `derive_metric_dims_from_evidence`. Si no, se usan dimensiones por defecto
   del arquetipo.
6. El builder parametrico crea una lista de partes. Cada parte contiene:
   - `primitive`: box, sphere, cylinder, cone, torus, etc.
   - `role`: cab, cargo, wheel, torso, head, leg, trunk, canopy, fallback volume.
   - `scale` y `local_pose`.
   - material role y metadatos de incertidumbre.
7. Se emite `SPPA-DESC-0.2` con `parts[]`, `semantic`, `resolver`, `scale`,
   `pose`, `uncertainty`, `material`, `runtime_policy` y presupuesto de coste.
8. Unreal lee el descriptor y crea componentes primitivos. En frames
   posteriores, si el arquetipo no cambia, se actualiza pose/confianza/material
   o parametros compatibles sin regenerar toda la topologia.

## Ejemplo: "cow" o mamifero

SPPA no pregunta en runtime si la vaca es un mamifero. Tampoco pregunta cuantas
patas tiene.

El conocimiento "cuadrupedo = torso + cabeza + cuatro patas" esta codificado en
una receta revisada. Esa receta puede haber sido escrita por una persona o
asistida por un LLM offline, pero para runtime ya es una tabla/programa
versionado.

Eso significa que:

- Si llega `cow` y esta cubierta, SPPA usa receta de vaca/cuadrupedo.
- Si llega `dog` o `horse` y solo tenemos familia generica, SPPA puede usar
  `quadruped` conservador.
- Si llega `cow poster`, `toy cow` o algo ambiguo visualmente, el gate debe
  preferir fallback antes que inventar un animal real.
- Si llega una especie no revisada con anatomia distinta, SPPA no debe
  inventarla: fallback o familia generica.

## Ejemplo: tractor y remolque

El sistema no necesita acertar "tractor" con precision taxonomica para demostrar
SPPA. Lo importante es que el detector de una aproximacion util, por ejemplo
`vehicle`, `agricultural vehicle`, `truck`, `trailer` o `heavy vehicle`, y que
SPPA lo normalice a una familia conservadora:

- `farm_vehicle` si la evidencia apunta a tractor/agricola.
- `heavy_vehicle` si la masa/forma se parece mas a camion/remolque.
- `generic_vehicle` si no hay especificidad suficiente.
- `unknown` si la etiqueta es inestable o sospechosa.

La virtud del paper no es que SPPA reconstruya un tractor perfecto. La virtud
real es convertir evidencia semantica imperfecta en un proxy 3D ligero,
controlable y seguro.

## Donde estaria la "trampa"?

La trampa seria vender esto como "un LLM genera cualquier objeto 3D desde texto"
o como "reconstruccion arbitraria". Eso no es lo que implementa SPPA.

La version honesta es mas fuerte para un paper de sistemas:

- No generamos geometria arbitraria perfecta.
- No hacemos razonamiento biologico o mecanico en vivo.
- No llamamos a un LLM en el loop de vuelo/render.
- Si la receta no esta revisada, se cae a fallback.
- La geometria viene de una biblioteca finita de recetas semanticas
  parametrizadas.

Esto no es una debilidad si se formula bien. En un dron real, una ruta
determinista, barata, revisable y con fallback explicito puede ser mas
defendible que una llamada generativa impredecible.

## Estado del arte: esto no es nuevo como idea geometrica

Combinar primitivas geometricas para representar objetos es una idea muy
estudiada. Algunos hitos relevantes:

| Linea | Referencias | Que hacen |
| --- | --- | --- |
| Geons / componentes | Biederman 1987, Marr y Nishihara 1978 | Representar forma con componentes volumetricos simples |
| Superquadrics | Solina y Bajcsy 1990; Paschalidou et al. 2019; SuperDec 2025 | Ajustar primitivas/supercuadricas a objetos o escenas |
| Primitivas aprendidas | Tulsiani et al. 2017; 3D-PRNN 2017 | Aprender ensamblajes de primitivas desde datos |
| CSG y programas | CSGNet 2018 | Parsear formas a programas CSG con booleanas sobre primitivas |
| Procedural / shape grammars | Mueller et al. 2006; ShapeAssembly 2020; ShapeCoder 2023 | Generar o descubrir programas compactos de forma |
| Texto a CAD / codigo CAD | Text2CAD 2024; CAD-Recode 2024/2025 | Generar secuencias CAD desde texto o point clouds |

Por tanto, la contribucion SPPA no debe formularse como "descubrimos que se
pueden combinar cubos/cilindros para crear objetos". Eso ya existe desde hace
decadas.

## Aportacion real defendible

La aportacion defendible esta en el contrato operativo:

1. Entrada de UAV: detecciones semanticas imperfectas, no mallas limpias.
2. Normalizacion SPPA: pasar de label ruidoso a familia revisada.
3. Recetas finitas: topologia semantica versionada, no generacion libre.
4. Descriptor/update: separar crear topologia de actualizar pose/confianza.
5. Unreal backend: actor primitivo intercambiable con assets curados.
6. Fallback conservador: desconocido no se convierte en objeto especifico.
7. Coste bajo: no requiere inferencia neural 3D en runtime.

Frase central recomendable:

> SPPA no promete reconstruccion arbitraria perfecta; promete convertir
> evidencia semantica imperfecta en proxies 3D ligeros, controlables y seguros.

## Que faltaria para una version mas ambiciosa

Para afirmar un "language-to-geometry" mas fuerte haria falta anadir trazabilidad
y evaluacion:

- Registrar modelos LLM offline concretos, prompts y salidas.
- Definir un schema de preguntas offline:
  - Que familia semantica es?
  - Que partes estables tiene?
  - Que primitiva representa cada parte?
  - Que dimensiones son adaptativas?
  - Que materiales pueden venir de observacion y cuales son priors?
  - Cual es el fallback si la etiqueta es ambigua?
- Crear un dataset de etiquetas/casos UAV con recetas esperadas.
- Medir errores de normalizacion, fallback correcto, coste y utilidad del proxy.
- Separar claramente benchmarks de imagen-a-3D de benchmarks de contrato SPPA.

## Fuentes principales consultadas

- ShapeAssembly: https://arxiv.org/abs/2009.08026
- ShapeCoder: https://arxiv.org/abs/2305.05661
- CSGNet: https://arxiv.org/abs/1712.08290
- 3D-PRNN: https://openaccess.thecvf.com/content_iccv_2017/html/Zou_3D-PRNN_Generating_Shape_ICCV_2017_paper.html
- Text2CAD: https://arxiv.org/abs/2409.17106
- CAD-Recode: https://arxiv.org/abs/2412.14042
- Procedural Modeling of Buildings: https://dl.acm.org/doi/10.1145/1141911.1141931
- Recognition-by-Components: https://pubmed.ncbi.nlm.nih.gov/3575582/
