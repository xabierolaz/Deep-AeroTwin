# JGSA BOARD AUDIT — 2026-07-18 (zero-trust, 3 agentes sin contexto previo)

**Método:** 3 agentes frescos sin contaminar (ninguno recibió nuestras conclusiones; solo rutas y rol):
- **Z1** = miembro del editorial board JGSA, lectura en frío del main + suplemento.
- **Z2** = auditor científico independiente de valor (zero-trust).
- **Z3** = perfil bibliométrico empírico de JGSA (20 papers reales 2023–2026 vía Crossref/Springer, 12 OA con conteos exactos).

Informes completos: `D:\Deep-AeroTwin-UE57-Test\sppa_audit\` (Z1), `D:\Deep-AeroTwin-UE57-Test\audit_sppa\AUDITORIA_SPPA.md` (Z2), `D:\Deep-AeroTwin-UE57-Test\jgsa_bibliometric_profile.md` (Z3).

---

## 1. Lo que JGSA publica de verdad (Z3, n=20)

- Páginas main: **12–25, mediana 17.5** · figuras **4–24, mediana 10.5** · tablas **0–6, mediana 2.5** · abstract ~217 palabras · ESM en solo **20 %** y corto · Data Availability 80 % · Code Availability 5–10 %.
- Estructura: **5–7 secciones** (Intro → [Related Work] → Materials & Methods → Results [+ Discussion] → Conclusion).
- Validación: **19/20 caso de estudio con datos reales**; 0/20 validación sintética prerregistrada.
- Tono: aplicado/geográfico; **figuras ≫ tablas**; secciones de sistemas/implementación: 1/20.
- Precedentes directos de tema: 3D city (2023), 3D roads (2026), virtual tours (2025), terrain-aware 3D (2025), UAV photogrammetry (2023, 2025).

## 2. Nuestras desviaciones detectadas (consenso de los 3)

| Desviación | JGSA | Nosotros | Severidad |
|---|---|---|---|
| Ratio figuras/tablas | 10.5 / 2.5 | **3 / 18 (invertido)** | CRÍTICA |
| Validación | caso real | sintética prerregistrada dominante | CRÍTICA |
| Suplemento | 20 %, corto | 21 págs ≈ el main | ALTA |
| Secciones 1er nivel | 5–7 | 14 | MEDIA-ALTA |
| Núcleo de sistemas (Unreal, latencias) | 1/20 | presente | ALTA |
| Tono defensivo | inexistente | "sealed" >40×, "preregistered" >15×, "not claimed" >20×, "honest" 4×, sección entera de Claim Boundaries | CRÍTICA (Z1: "25–30 % del main es gestión defensiva") |

## 3. Auditoría de valor de elementos SPPA (Z2)

- **(A) Realmente valioso:** aparato de medición (preregistro/sellado/equal-budget); test externo negativo (+0.043 n.s., hull 0.656, cápsula/caja ≥ SPPA); descomposición 2×2 + familia errónea (−0.162: prior malo peor que ninguno); asimetría de corrupciones (morfología contradictoria duele más que máscara ruidosa).
- **(B) Ya existe (renombrado):** contrato runtime ≈ replication/entity-state (DIS/HLA, rviz Marker, Unreal replication); grafo de partes ≈ 3DMM/SMPL/PartNet; fitting ≈ pattern search 1961 + Solina-Bajcsy 1990; fallback ≈ open-set rejection; Unreal/HISM = instancing estándar.
- **(C) No aporta medida:** benchmarks round-trip con error 0.000 (tautologías); stress test legacy (autodeclarado superseded); tabla de conteos de ontología; link-budget modelado; batería anti-shortcut (tests de software, no evidencia); probes YOLOE n=4 sin GT (ejercitan plumbing); role-aware IoU (control shuffle, estrato circular — débil como prueba de utilidad de roles).

## 4. Cortes convergentes (Z1+Z2+Z3)

1. **Eliminar §13 Claim Boundaries como sección** + fusionar §12 Threats en §11 Discussion (3 frases de frontera en conclusión). (~0.8 pp)
2. **Párrafo LLM → 2 frases; eliminar tabla de ontología y sus conteos.** (~1.1 pp)
3. **§9 neural → ~10 líneas en main; tabla y "Reading" al suplemento; eliminar reconciliación 3.09M/1.7M.** (~1.2 pp)
4. **§10 probes → 2 párrafos + tabla runtime condensada; resto al suplemento.** (~1.0 pp)
5. **Related Work: matar dump de generadores, párrafo "cited but not executed", SAGAT/TLX; bookkeeping de protocolo (amendments, NIST, potencia) y spec sheet → suplemento/footnote; drop-one-family y budget-sweep → suplemento.** (~1.2 pp)
6. **Suplemento: eliminar S.4 legacy + stress test superseded (→ 5 líneas) + round-trips 0.000 + anti-shortcut/diario → 21 → <10 págs.**
7. **Colapsar 14 secciones → 7** (plantilla JGSA: Introduction / Related Work / Materials & Methods / Method / Results / Discussion / Conclusion + Data Availability).
8. **Inversión figuras/tablas:** 18 → 4–6 tablas; 3 → 10–15 figuras (renders, heatmaps de error, curvas, ejemplos de probes; las tablas detalladas al suplemento).
9. **Reencuadre de validación:** las 52 mallas reales + probes como "case study" (patrón de la casa); la batería sintética prerregistrada como subsección.
10. **Abstract ~200–250 palabras**; o incluir el dato incómodo (cápsula/caja ≥ SPPA externo) o no mencionar externo; purgar metalenguaje ("sealed", "honest", "preregistered" al mínimo; el protocolo se describe una vez en Methods).
11. **Añadir Data Availability** (+ Code Availability si el repo se libera: diferenciador, solo 5–10 % lo tiene).
12. **Título sin jerga interna** ("SPPA-MVFit" no significa nada para un editor JGSA).

## 5. Veredicto del board (síntesis)

**El paper científicamente defendible de 16–18 páginas está enterrado dentro de un paquete de 45.** El rigor salva del desk reject, pero el registro (tono defensivo, inversión figuras/tablas, validación sintética dominante, suplemento-diario) es hoy el principal riesgo de rechazo en JGSA — no la ciencia. La transformación es editorial, no experimental: misma evidencia, nuevo envoltorio.

## 6. Riesgo a vigilar en la transformación

- No ocultar el aparato prerregistrado: es la (A) más valorada; moverlo de *protagonista* a *Methods* (una subsección), no eliminarlo.
- No inflar el "case study": las 52 mallas son sanity check con mapeo aproximado; presentarlas como lo que son.
- El abstract debe decidir: o dice el resultado externo completo (incluido cápsula/caja ≥ SPPA) o no lo dice; la versión intermedia (margen no transferido sin los baselines) le pareció ocultación a Z1.
