# Checklist de validacion hardware/HMD/geoespacial

Estado: checklist operativo para sustituir placeholders del paper.

## HMD y Unreal

- modelo HMD;
- runtime OpenXR/SteamVR/Meta/etc.;
- refresco configurado;
- resolucion o escala render;
- modo seated/standing;
- metodo de captura HMD;
- version Unreal;
- version Cesium;
- commit del proyecto;
- configuracion de `UPorceTelemetryComponent`;
- endpoint `GET /api/ui/data`;
- frecuencia de polling.

## Latencia fuente-HMD

Registrar timestamps:

1. deteccion o replay source event;
2. envio `POST /api/obstacles`;
3. recepcion Brain;
4. reconstruccion de estado Brain;
5. respuesta `GET /api/ui/data`;
6. recepcion Unreal;
7. actor spawn/update;
8. frame visible en HMD.

Resultado minimo:

- media, p50, p95, p99;
- waterfall por componente;
- reloj/sincronizacion usada;
- perfil de red.

## Georreferenciacion

Registrar:

- intrinsecos de camara;
- extrinsecos camara-UAV;
- pose UAV;
- actitud/yaw/pitch/roll;
- origen local/home;
- modelo de terreno;
- ground truth: RTK/GNSS, topografia, motion capture o medicion equivalente;
- metodo de asociacion deteccion-ground truth.

Resultado minimo:

- error 2D;
- error 3D si procede;
- error por rango;
- error por clase;
- incertidumbre mostrada vs error real.

## Red

Registrar:

- tipo de enlace;
- ancho de banda disponible;
- perdida;
- jitter;
- retardo;
- interrupciones;
- herramienta de emulacion si se usa.

## Objetos y tracking

Registrar:

- objetos presentes;
- trayectorias ground truth;
- aparicion/desaparicion;
- oclusiones;
- cambios de ID;
- stale duration;
- despawn correctness.

## Evidencia visual

Capturar:

- HMD con UAV, terreno y actores;
- actor fresco;
- actor stale;
- actor con incertidumbre;
- despawn;
- interrupcion de enlace;
- recuperacion.

Cada imagen debe tener:

- fecha;
- commit/configuracion;
- escenario;
- que placeholder sustituye.
