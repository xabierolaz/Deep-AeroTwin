# Protocolo preliminar de estudio con operador HMD

Estado: borrador operativo. No usar como resultado experimental hasta ejecutar
el estudio, aprobar/eximir la etica y analizar datos reales.

## Objetivo

Evaluar si la pantalla VR/digital twin de Pipeline B ayuda al operador UAV a
localizar, recordar y razonar sobre objetos relevantes cuando el video o el mapa
no bastan por campo de vision limitado, degradacion de enlace o perdida
intermitente de detecciones.

## Pregunta primaria

Comparado con interfaces video-only, map-only y desktop-hybrid, el display HMD
de Pipeline B mejora la conciencia espacial o el exito de tarea sin aumentar de
forma inaceptable la carga cognitiva, la cibermareo o la confianza excesiva en
actores obsoletos?

## Condiciones experimentales

1. Video-only: operador ve solo video o replay de video.
2. Map-only: operador ve mapa/posicion sin escena inmersiva.
3. Desktop-hybrid: operador ve mapa + entidades en una pantalla 2D/3D no HMD.
4. VR digital twin: operador usa HMD y ve terreno, UAV, actores, frescura e
   incertidumbre.

## Tareas

Cada participante debe realizar tareas comparables:

- identificar el numero de objetos relevantes en la escena;
- localizar objetos respecto al UAV, ruta o infraestructura;
- recordar si un objeto sigue activo, esta obsoleto o ha desaparecido;
- decidir si una ruta o area requiere atencion del piloto;
- detectar cuando el sistema esta mostrando informacion stale o incierta.

## Variables independientes

- interfaz: video-only, map-only, desktop-hybrid, VR digital twin;
- degradacion del enlace: nominal, perdida moderada, jitter, interrupcion corta;
- tipo de objeto: bike, cow, tower u otros que se validen;
- visibilidad/deteccion: deteccion continua, oclusion, falsos negativos.

## Variables dependientes

Primarias:

- exito de tarea;
- puntuacion de conciencia espacial;
- errores de localizacion;
- deteccion correcta de estados stale/inciertos.

Secundarias:

- tiempo de respuesta;
- near misses o decisiones inseguras simuladas;
- NASA-TLX o equivalente de carga de trabajo;
- SART/SAGAT o equivalente de situational awareness;
- SSQ o escala equivalente de cibermareo;
- cuestionario de confianza/overtrust.

## Diseno recomendado

Diseno within-subject si el numero de participantes es limitado. Cada
participante prueba todas las condiciones en orden contrabalanceado. Usar
escenarios equivalentes pero no identicos para reducir aprendizaje.

## Criterios de inclusion

- adulto con vision normal o corregida;
- capacidad para usar HMD;
- sin contraindicacion conocida para VR;
- experiencia UAV registrada como covariable, no necesariamente requisito.

## Criterios de exclusion

- cibermareo severo durante entrenamiento;
- incapacidad de completar condicion minima;
- problemas tecnicos HMD/tracking que invaliden una prueba;
- retirada voluntaria.

## Material a registrar

- version del software;
- modelo HMD, refresco, runtime, resolucion;
- escenario y condicion;
- timestamps de eventos;
- respuestas del operador;
- metricas objetivas;
- cuestionarios;
- incidencias tecnicas;
- video/captura si esta aprobado por etica y privacidad.

## Riesgos a controlar

- overtrust: el participante puede creer que el actor stale es real;
- cibermareo;
- fatiga;
- interpretacion de un prototipo como sistema certificado;
- privacidad si se usan capturas reales.

## Resultado esperado para el paper

La seccion de resultados debe informar, como minimo:

- numero de participantes y perfil;
- diseno y contrabalanceo;
- metricas primarias/secundarias;
- efecto de la interfaz sobre conciencia espacial y tarea;
- carga de trabajo y cibermareo;
- fallos/limitaciones del display.
