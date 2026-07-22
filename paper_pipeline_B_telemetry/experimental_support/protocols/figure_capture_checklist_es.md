# Checklist de figuras y material suplementario

Estado: guia para producir figuras sin sobreactuar resultados.

## Figuras recomendadas

1. Arquitectura runtime
   - Ya existe en el paper.
   - Debe seguir marcada como flujo propuesto/implementado, no como resultado.

2. Contrato de datos
   - `POST /api/obstacles` -> Brain -> `GET /api/ui/data` -> Unreal.
   - Mostrar campos clave: `entity_id`, `type`, `confidence`, `world_m`,
     `track_age_s`, `uncertainty`.

3. Ciclo de vida actor
   - spawn;
   - update;
   - stale;
   - remove/despawn.

4. Captura HMD real
   - terreno;
   - UAV pose;
   - actor vivo;
   - confianza;
   - edad/frescura;
   - incertidumbre.

5. Instrumentacion de latencia
   - fuentes de timestamp;
   - reloj;
   - componentes del waterfall.

6. Resultados
   - bandwidth vs video;
   - latency waterfall;
   - geospatial error;
   - degradation/loss;
   - human utility.

## Reglas

- No usar mockup como evidencia.
- Si una figura es conceptual, decirlo en caption.
- Si una captura es replay/sintetica, decirlo en caption.
- Si la figura viene de HMD real, guardar commit/configuracion/logs.
- Evitar capturas que oculten incertidumbre o stale state.

## Video suplementario

El video deberia mostrar:

- llegada de deteccion;
- spawn;
- actualizacion de posicion;
- perdida/interrupcion;
- stale visual;
- recuperacion;
- despawn;
- vista del operador.

Guardar:

- archivo fuente;
- duracion;
- resolucion;
- codec;
- escenario;
- permiso si aparecen personas o datos reales.
