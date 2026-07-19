# HANDOFF PARA CLAUDE CODE — SPPA-MVFit (JGSA submission)

**Fecha:** 2026-07-19 · **Autor del handoff:** Kimi Work · **Estado:** build sano, pendiente commit y cierre de envío.

---

## 0. Cómo trabajar aquí (léelo antes de tocar nada)

- **Directorio del paper:** `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d`
  (= `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d` por junction NTFS; son LA MISMA carpeta).
- **Repo git:** raíz en `D:\Deep-AeroTwin-UE57-Test` (GitHub `xabierolaz/Deep-AeroTwin`). El paper entra vía junction.
- **NO HACER COMMIT sin confirmación explícita del usuario.** Lleva pendiente varias sesiones; pregúntale siempre.
- **No modificar NUNCA** `reproducibility/sppa_mvfit/` (artefactos sellados preregistrados) ni los números del benchmark primario.
- **Honestidad primero:** varios resultados del paper son negativos a propósito (external, real stream). Nunca "mejorar" números; reportarlos tal cual.
- Al compilar LaTeX: **borra el PDF antes** (se bloquea a veces por visores/indexadores) y usa los **nombres canónicos** (sin `-jobname`).
- Python: `C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe` con `PYTHONUTF8=1`.
- Historial completo del proceso: `kimi_code.md` (este mismo directorio) y `editorial_audits\20260718\`.

## 1. Estado actual verificado (2026-07-19)

- `semantic_proxy_3d_paper.pdf`: **23 páginas, 15 figuras, 7 tablas** — 0 refs/citas indefinidas, 3 overfull menores (≤12.9 pt).
- `semantic_proxy_3d_submission_supplement.pdf`: **10 páginas**, secciones S.1–S.9 — 0 indefinidas.
- Integrados esta sesión (main + suplemento):
  - **E8 adversarial** (`benchmarks\mvfit_reviewer_experiments\e8_adversarial_family\`): violar el prior estructural recorta la ventaja de +0.209 a +0.141 [0.125,0.157] (destruye ~1/3; empates en lattice inclinada 25° y cascade crown). Rompe la crítica de tautología con datos. §"Adversarial family instances" en main, tabla en S.9.
  - **E9 part-query** (`...\e9_role_query\`): tarea operacional de consulta de parte: F1 0.434 (SPPA) vs 0.145 (generic) / 0.111 / 0.087 (hull heuristics); conteo exacto 70% vs 0%. Justifica cuantitativamente los roles. Párrafo "Part-query task" en main, tabla en S.9.
  - **E7 real stream** (`benchmarks\real_stream_wave\`): 1902 detecciones de un stream real de 1394 frames (detector custom real, telemetría mavlink, GT exacto de 11 torres). Resultados honestos: TODOS los métodos observation-bound a ~33 m (y=x); SPPA **no gana** el IoU 2D de reproyección (0.298 vs 0.42–0.45 cajas) — el prior cambia solape 2D por estructura 3D; brazo token erróneo real: refit con token correcto colapsa 0.381→0.025; latencia 11.8 ms. §"A real detector stream case study" en main (tabla+figura), token-arm en S.9.
  - Intro con contribuciones (i)(ii)(iii) explícitas; Discusión y Threats actualizados (tautología declarada + límites del stream); Abstract y Conclusión incluyen adversarial + stream.
- Compilación: `export PATH="/c/Program Files/MiKTeX/miktex/bin/x64:$PATH"`, luego `pdflatex` ×2 (main) y ×2 (suplemento) con `-interaction=nonstopmode -halt-on-error`. El aviso "User/administrator updates are out-of-sync" de MiKTeX es ruido inofensivo.

## 2. Números que NO deben cambiar (sellados/verificados)

H1 = +0.190 [0.181,0.199] (n=240, margen +0.030 PASS); estratos 0.209/0.172; robustez 0.118–0.190; 2×2: 0.180/0.427/0.367/0.557; wrong-family 0.205 (−0.162, 98.3%); top-only 0.458, side-only 0.545; OBB 0.252 ≈ AABB 0.248; budget 0.528/0.547/0.557/0.560; role-aware 0.319 vs 0.053/0.017; externo n=52: 0.413/0.370/0.656 hull/0.492 cápsula, Δ+0.043 [−0.007,+0.094]; timings: 9.43 ms mediana sellado / 12.6 ms re-run sweep (ya explicado en texto).
Nuevos (post-hoc exploratorios): E7 ver tabla main; E8 +0.141 [0.125,0.157], ΔΔ −0.068, pierde 8.3%; E9 F1 0.434/0.145/0.111/0.087, d_c 0.055, conteo 70%.

## 3. Lo que queda (en orden)

1. **Puerta strict** (valida artefactos sellados; debe dar 0 blockers):
   `cd /d/Deep-AeroTwin-UE57-Test && PYTHONUTF8=1 /c/Users/xabie/AppData/Local/Programs/Python/Python312/python.exe paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict`
2. **Acta R7**: crear `editorial_audits\20260719\TRIBUNAL_ROUND_07.md` resumiendo E7/E8/E9 (formato: ver `editorial_audits\20260718\TRIBUNAL_ROUND_06.md`).
3. **kimi_code.md**: añadir bloque 2026-07-19 con este estado.
4. **Commit**: SOLO si el usuario confirma. Alcance: todo lo de `paper_semantic_proxy_3d/` (paper, benchmarks nuevos E7/E8/E9, figuras, actas, handoffs). NO tocar cambios de `Unreal/`, `XYT-xabi-yolo-telemetry/`, `docs/` (otra línea de trabajo). Las mallas externas (~750 MB) ya están en `.gitignore`.
5. **Decisión DOI**: Data Availability dice "upon publication" sin repo ni DOI → proponer Zenodo o repo institucional UPNA antes de enviar (riesgo editorial si se deja).
6. **Checks del día de envío** (lista en `JOURNAL_DECISION_20260716.md`): APC Springer/CRUE con biblioteca UPNA, JCR Q1 vigente, guía de autor JGSA (anonimato si aplica).

## 4. Claude Code en esta máquina (ya verificado)

- CLI: `C:\Users\xabie\.local\bin\claude.exe` (v2.1.198). Extensión `anthropic.claude-code` instalada en Cursor (fork de VSCode).
- **Modo autónomo YA configurado:** `C:\Users\xabie\.claude\settings.json` tiene `permissions.defaultMode = "bypassPermissions"` + allow-list (Bash/Read/Edit/Write/Glob/Grep/WebFetch/WebSearch). No debería pedir permisos. Si alguna vez aparece un aviso de "dangerous mode" al arrancar, es una confirmación única; y el "Workspace Trust" de VSCode/Cursor es aparte (marca la carpeta como trusted).
- Ese settings.json contiene un token de API (proxy z.ai). **No lo copies a ningún archivo del repo ni lo imprimas.**
- Arranque sugerido: abrir `D:\Deep-AeroTwin-UE57-Test` en Cursor y lanzar Claude Code ahí; o por terminal: `cd /d D:\Deep-AeroTwin-UE57-Test && claude --dangerously-skip-permissions`.

## 5. Respuesta a las dos preguntas del usuario (contexto editorial)

- **Novelty:** queda explícita en el intro como (i) protocolo input-matched equal-budget preregistrado, (ii) mapa de frontera cuantificado (wrong-family, adversarial, 1-vista, externo, stream real), (iii) contrato de actor ligero con valor medido por part-query. No es "otro image-to-3D".
- **Comparativa justa:** todos los métodos reciben la MISMA observación en cada experimento (sellado sintético, externo, stream real), mismo presupuesto de fitting para los dos MVFit, y los resultados negativos se reportan sin filtrar. E7 es exactamente el escenario "rápido desde input de vuelo real": latencias 0.22–13.4 ms/caso, con SPPA perdiendo el IoU 2D y ganando estructura/roles — declarado en el paper.
