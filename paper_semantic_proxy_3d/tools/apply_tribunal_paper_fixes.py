from __future__ import annotations

import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "semantic_proxy_3d_paper.tex"
tex = path.read_text(encoding="utf-8")

marker = "\\section{Primary Results}\n\\label{sec:primary-results}\n\n"
insert = (
    "\\section{Primary Results}\n\\label{sec:primary-results}\n\n"
    "\\paragraph{Spatial estimand.}\n"
    "The spatial quantity under test is object-level occupancy of a lightweight proxy\n"
    "actor in a shared metric twin frame. Calibrated orthographic top and side\n"
    "silhouettes provide two projected occupancy constraints; 64-cubed voxel IoU is the\n"
    "spatial-quality metric against independent synthetic source occupancy. Family\n"
    "tokens are observed inputs that select a frozen part graph (a spatial prior over\n"
    "role-labeled volumes), not inferred open-set labels. This is a synthetic\n"
    "spatial-proxy evaluation for digital-twin display actors; it is not a cartographic\n"
    "map task and not a measured UAV sensing product.\n\n"
)
if marker not in tex:
    raise SystemExit("marker1 missing")
tex = tex.replace(marker, insert, 1)

a = tex.index("H1 passes: mean")
b = tex.index("\\section{Secondary Systems Evidence}")
new_res = r"""H1 passes: mean \(\Delta\mathrm{IoU}=0.190\) with 95\% CI \([0.181,0.199]\).
The confirmatory estimand is the equal-stratum paired mean difference;
Table~\ref{tab:mvfit-means} is descriptive. The CSG-ID stratum mean difference is
\(0.209\) and the implicit-OOD stratum mean difference is \(0.172\); neither is
non-positive. Table~\ref{tab:mvfit-family} reports all twelve family$\times$stratum
cells from the sealed analysis: every cell is positive, with the smallest gain on
compact vehicles under implicit-OOD (\(\Delta=0.043\)) and the largest on
rider-cycle under CSG-ID (\(\Delta=0.458\)).
Figure~\ref{fig:mvfit-h1} shows illustrative held-out occupancy for three families.

SPPA-MVFit exceeds SPPA text-only (mean \(\Delta=0.130\), CI \([0.117,0.143]\)) and
lightweight geometric baselines. Mean IoU of SPPA-MVFit (\(0.557\)) is slightly above
the classical nonsemantic visual hull (\(0.522\))~\cite{laurentini1994visualhull}, but
visual hull is denser free occupancy without an eight-part role-labeled actor
contract; it is a high-complexity geometry reference, not a defeated runtime
competitor. Secondary comparisons use the same stratified bootstrap intervals;
null-centered bootstrap \(p\)-values with Holm adjustment are recorded in the
analysis artifact (Amendment~04). Single-pass clean-call wall time for SPPA-MVFit
during the sealed evaluation is median \(9.4\)~ms (p95 \(10.6\)~ms) on the benchmark
machine; this is not a warm-timing Unreal frame-time claim and is not the protocol
H4 multi-call cost design. A resolution-sensitivity check at grids 48/64/80 on the
prespecified actor subset passes the protocol threshold. Candidate silhouette
renders during fitting used the executed \(96\times 96\) observation grid on both
arms (Amendment~04 alignment of protocol text with frozen code).

\begin{table}[H]
\centering
\footnotesize
\caption{Sealed family$\times$stratum clean-mask mean $\Delta$ IoU
(SPPA-MVFit $-$ Generic-MVFit). All twelve cells are positive.}
\label{tab:mvfit-family}
\input{benchmarks/results/sppa_mvfit_family_strata.tex}
\end{table}

\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{figures/sppa_mvfit_h1_occupancy_examples.png}
\caption{Illustrative synthetic occupancy for three held-out morphology cases
(ground-truth source, Generic-MVFit, SPPA-MVFit). The figure is qualitative
support for the tables; the confirmatory decision is Table~\ref{tab:mvfit-h1}.}
\label{fig:mvfit-h1}
\end{figure}

\noindent\textcolor{red}{Claim boundary: these occupancy gains are measured on
synthetic calibrated silhouettes with known family tokens. They are not UAV
flight measurements, not detector accuracy, and not operator-facing benefit.}

"""
tex = tex[:a] + new_res + tex[b:]

start = tex.index("\\section{Secondary Systems Evidence}")
end = tex.index("\\section{Discussion}")
secondary = r"""\section{Deployment Context (Secondary)}
\label{sec:secondary-context}

Outside the confirmatory endpoint, SPPA also exposes a versioned descriptor/update
contract and an optional Unreal Engine backend that can coexist with curated assets
on the same obstacle payload. Local engineering regressions support open-label
recipe gating, connector primitives, and limited packaged desktop actor/HISM
coexistence. Four user-supplied real images are used only as qualitative detector
probes under declared replay assumptions; they have no 3D ground truth and do not
support real-UAV reconstruction accuracy, SOTA image-to-3D ranking, or measured
flight claims. Dense VR readiness, operator benefit, and radio-link advantage remain
untested. Full historical systems tables live in the artifact archive, not in this
submission body.

"""
tex = tex[:start] + secondary + tex[end:]

tex = re.sub(
    r"Sixth, the Holm[s-]*style secondary \$p\$-values in the analysis artifact are not used in\s+this manuscript; secondary inference is reported via bootstrap intervals only\.",
    "Sixth, secondary inference uses stratified bootstrap intervals; null-centered bootstrap $p$-values with Holm adjustment are recorded in the sealed analysis artifact after Amendment~04. Seventh, the pre-test protocol release used a written local triple-role audit under Amendment~03 after external review infrastructure failure; it is not external peer review.",
    tex,
    count=1,
)

# Compress related-work laundry list if still long - soft touch
tex = tex.replace(
    "Text-to-3D and image-to-3D generation methods such as DreamFusion, Magic3D,\n"
    "Point-E, Shap-E, TripoSR, TripoSG/Tripo P1, InstantMesh, Stable Fast 3D,\n"
    "SPAR3D, LGM, CRM, Unique3D, Direct3D-S2, PartCrafter, Pixal3D,\n"
    "TRELLIS/TRELLIS.2, Hunyuan3D 2.x, and commercial systems such as Rodin Gen-2.5 target visual asset generation or\n"
    "reconstruction",
    "Text-to-3D and image-to-3D generation methods such as DreamFusion, Magic3D,\n"
    "Point-E/Shap-E, InstantMesh/Stable Fast 3D, and TRELLIS/Hunyuan3D-class systems\n"
    "target visual asset generation or reconstruction",
)

path.write_text(tex, encoding="utf-8")
print("ok", path)
print("sections:", [ln for ln in tex.splitlines() if ln.startswith("\\section")])
print("chars", len(tex))
