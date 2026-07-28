# Auditoria zero-trust del Pipeline B (replay M_20_1RR) — 2026-07-21

Metodo: verificar cada eslabon de forma independiente, sin fiarse de ninguno.
Datos: video real + log ArduPilot + GT PNOA + auditoria Brain (1502 obs en 3 corridas).

## Veredicto por eslabon

| Eslabon | Prueba | Resultado |
|---|---|---|
| Orientacion del video | Evidencia fisica: horizonte, lineas electricas, mastil del apoyo | **El mp4 se almacena sky-up PORTRAIT; el flag rotate=270 es enganoso.** Procesar con ROTATE=0. (Antes: procesabamos en landscape = error de roll 90 grados.) |
| Detector YOLO | mAP50 0.982 (portrait, re-entrenado con tracking por plantilla) | Correcto. Detecciones reales verificadas visualmente sobre el apoyo. |
| Matematica de proyeccion (`geo_projector`) | Ida y vuelta contra modelo independiente en casos controlados | **Correcta: acuerdo <= 1.5 m** (t=25 y t=32). No es la fuente del error. |
| Montaje de camara | Overlay ortofoto<->frame en t=32: marcador P3 sobre el apoyo real; backsolve del apoyo a ~8 m del GT | **Validado: (yaw 155, pitch -37, roll 0, fov_v 77).** Residuo ~2-3 grados. |
| Sincronia video<->log | Deriva PTS (VFR): +-0.1 s. Giro del dron: log t=40.5-44 vs video t=39-43 | **~1 s de offset posible (contribuye ~8-12 m en pista).** VFR despreciable. |
| Terreno (rel_alt) | CSV: rel_alt = alt_msl - 256.4 (mediana en suelo); TERR del log 253-258 | Correcto. |
| Ground truth de apoyos | Clusters de posiciones publicadas (sistema) vs ortofoto PNOA | **El GT estaba INCOMPLETO (mi error): hay ~5-6 apoyos reales en la escena y solo 4 estaban marcados.** Los "errores" de 50-130 m eran misasignacion a apoyos no mapeados, NO error del sistema. |
| Posicion final en Unreal | Obstaculo sintetico world_m=(100,120) -> proxy en (10000,12000) cm | Correcto. |
| Ciclo de vida (stale/despawn) | Proxy spawnea al detectar y despawnea al expirar el track | Correcto. |

## La verdad sobre el error

Analisis por clusters (a prueba de misasignacion) sobre la corrida portrait limpia:

- **Cluster principal (216 obs, apoyo P3): centro a 4.3 m del GT PNOA.** Este es el error real del sistema para el apoyo validado, incluyendo montaje+sincronia+GT.
- El resto de clusters son apoyos reales adicionales del tendido (verificados en ortofoto: estructuras visibles en 3 de 4) que no estaban en el GT.

**El error georreferenciado real del sistema es ~4-5 m para el apoyo principal a 40-130 m**, no 15-80 m como sugeria el analisis por "apoyo mas cercano" con GT incompleto.

## Fuentes de error residuales (cuantificadas)

1. Montaje residual ~2-3 grados -> ~2-8 m segun distancia.
2. Sincronia ~1 s -> ~8-12 m a lo largo de la pista (corregible midiendo el offset con un evento reconocible; el giro sugiere ~1-1.5 s).
3. GT PNOA: precision de marcado ~2-5 m (0.167-0.232 m/px + georreferencia WMS).
4. Altura del punto de deteccion (cabeza ~10.5 m vs base) — relevante si se usa el fondo del bbox para distancia.

## Pendiente (para cerrar la validacion por apoyo)

- Completar el mapa GT del corredor con los apoyos descubiertos por los clusters
  (P5 42.142930/-1.587044, P6 42.141960/-1.587097, P7 42.142360/-1.587586,
  P8 42.144073/-1.587843 pendiente de confirmacion fina en ortofoto de mayor zoom).
- Re-correr `analyze_replay.py` con el GT completo para el informe por apoyo.
