# REFRAME PLAN — SPPA-MVFit (JGSA) — 2026-07-20

**Decisión del usuario (2026-07-20):** reencuadrar el paper a la novedad real y podar lo que no se use. Título NUEVO aprobado:
> **"Instant Semantic Proxy Reconstruction for UAV Digital Twins under Degraded Sensing (SPPA-MVFit)"**

**Novedad (enunciado fijado):** generación instantánea de volumen de alta fidelidad con geometría mínima, desde la evidencia que haya — robusto a señal de imagen débil y a degradación sensorial (noche/niebla/humo, LiDAR intercambiable por diseño). Misión: pilotaje remoto seguro en twin Cesium/Unreal cuando la imagen real no basta; Cesium ≠ realidad actual (animales, personas, torres nuevas/movidas) y SPPA reconstruye exactamente ese delta, al instante y a ancho de banda de telemetría. Scope: posición dada (localización = otro paper); solo fidelidad de reconstrucción.

**Base:** dos auditorías externas independientes (editorial ciega + verificación de evidencia), 2026-07-19/20. Convergen en este plan.

## ELEVAR a titular
- Robustez prerregistrada a corrupción de máscara (§4.2 → subsección headline; figura standalone; tabla S.9 → main): ruido de máscara cuesta ~0.001 IoU; morfología 0.118 ≫ margen. ES la evidencia "señal débil".
- Latencia 11.8 ms en stream real vs 2–15 Hz (→ abstract + §4.10).
- Link budget medido 25.8–37.4 kB/s JSON vs ≥250 kB/s vídeo modelado (S.8 → fila en tabla runtime + abstract).
- Validación de tokens: AUC −conf 0.847; AUC(−mismatch) 1.000 (mecanismo invertido documentado).
- Ola neural con 4 generadores (E12): eje competidor medido, mantiene disclaimer "input-modality mismatch, not a leaderboard".

## PODAR → suplemento
- Figuras: probes-grid, external-gallery, fitting-sequence, runtime-scaling (→ filas de tabla runtime), paneles (b)(d) de fig_real_stream, Alg. 1.
- Tablas: mvfit-secondary (T4), surface-metrics (T5). OBB ¶ → suplemento. Open-label probe ¶ → suplemento.
- ¶ "Language model use" (una cláusula basta); detalle descriptor_id/scheduler; custodia de seeds/NIST (una frase + puntero).
- Columnas de localización/footprint de la tabla real-stream.

## ELIMINAR
- Prescripciones de vistas de vuelo (órbitas/pasadas) en §4.6, §4.10 cierre, Discussion (×2). Reemplazo: "el modo top-only cuantifica el régimen nadir"; sin recomendar órbitas ni "production".
- Narrativa de mode-routing refutado (queda solo token validation).
- "In production" sin referencia.
- Discusión de localización de E7 (~33 m observation-bound) → una frase + suplemento (fuera de scope).

## AÑADIR
- **Figura de misión** (3 paneles: mundo real con intruso / twin Cesium obsoleto sin él / twin con proxy SPPA insertado; anotaciones 1.45 kB y ~10 ms) en el hueco de fig:pipeline-overview (que pasa al suplemento).
- ¶ de misión en §1 (piloto remoto VR; Cesium congelado; SPPA reconstruye el delta).
- Argumento sensor-agnóstico en §3.2: cualquier sensor que produzca huella geoproyectada entra por el mismo contrato (cámara validada; LiDAR = diseño declarado, NO medido).
- Reescritura: abstract, ¶ de pregunta de investigación, contribuciones (i)(ii)(iii) → (i) camino instantáneo detección→volumen (9.4 ms CPU, 1.45 kB, 11.8 ms en stream real); (ii) evidencia prerregistrada de fidelidad volumétrica + robustez a señal débil (+0.190 [0.181,0.199], mantenido bajo corrupciones prespecificadas; frontera medida); (iii) contrato de actualización del delta del twin (25.8–37.4 kB/s medido, part-query F1 0.434, límites declarados). Discussion ¶1 y Conclusion reordenados (misión → robustez → contrato → límites).

## LÍNEAS ROJAS (nunca afirmar; declarar)
LiDAR (no medido — salvo E14 si se ejecuta); noche/niebla/humo (solo corrupción sintética de máscara prerregistrada); VR end-to-end (no medido); beneficio de operador (sin estudio humano); 60 FPS en shape updates densas (no alcanzado — T7); "instant" = por objeto/track (9.4 ms fit; packaged denso limitante, ya declarado); "1.45 kB" = update descriptor compacto (el JSON completo del replay es ~8.4 kB — usar "compact update descriptor"); robustez = post-hoc sobre datos sellados (etiquetar así).

## EXPERIMENTOS EN CURSO (post-hoc exploratorios; sellos intactos)
- **E11** (captura completa 308/308 frames, 0 fallos, GT exacto en gt/): análisis = fits por ángulo con detector real + consistencia entre vistas + fidelidad vs GT exacto (voxel IoU vs tower OBJs), posición bloqueada. Sostiene: "la reconstrucción se mantiene a través de las vistas que el vuelo entrega, y es fiel al GT".
- **E14** (nuevo): demo LiDAR-en-el-twin (noche/niebla, sin cámara): raycasts → cluster → huella → proxy vs GT exacto. Sostiene la narrativa de degradación sensorial con datos.
- Integración en dos pasadas: (1) reestructura + E12/E10 ya integrados; (2) E11/E14 cuando aterricen.

## VERIFICACIÓN FINAL (obligatoria)
Compilación limpia main+suplemento (0 indefinidas), puerta strict 0 blockers, acta R7 actualizada, bloque kimi_code.md 2026-07-20. Sin commits sin confirmación del usuario.
