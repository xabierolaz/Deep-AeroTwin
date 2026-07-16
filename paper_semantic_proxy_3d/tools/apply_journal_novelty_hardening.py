"""Harden novelty clarity and journal-acceptance packaging in the main TeX."""

from __future__ import annotations

from pathlib import Path

PAPER = Path(__file__).resolve().parents[1] / "semantic_proxy_3d_paper.tex"


def main() -> int:
    tex = PAPER.read_text(encoding="utf-8")

    # --- Abstract: front-load novelty in one sentence ---
    old_abs = r"""\begin{abstract}
Object-level UAV telemetry is not a mesh: a detector may provide a class family,
confidence, track identifier, bounding region, and approximate pose, but no
occupancy geometry. This paper studies whether a frozen semantic-family part
graph improves lightweight 3D occupancy relative to an input-matched,
equal-budget nonsemantic graph when both consume the same calibrated top and
side silhouettes. The method, family-conditioned SPPA-MVFit, adjusts five shared
parameters of a fixed eight-part primitive actor with a 31-candidate silhouette
objective; text-only and silhouette-fitted modes call the same actor builder.

On a preregistered developer-held-out synthetic test of 240 actors balanced
across six morphology families and two source strata (CSG-ID and structurally
different implicit-OOD), the primary paired mean voxel-IoU difference of
SPPA-MVFit minus Generic-MVFit is \(0.190\) with stratified bootstrap 95\% CI
\([0.181,0.199]\). The lower bound exceeds the prespecified \(+0.030\)
superiority margin, so the primary hypothesis passes. Both strata remain
positive (\(0.209\) CSG-ID; \(0.172\) implicit-OOD). Secondary comparisons
favour SPPA-MVFit over text-only SPPA and lightweight geometric baselines;
median clean-call wall time is \(9.4\)~ms (p95 \(10.6\)~ms) on the benchmark
machine. The result is synthetic internal evidence only: it does not establish
real UAV reconstruction, measured flight validity, operator benefit, or an
image-to-3D SOTA ranking. A separate SPPA descriptor/update contract and
optional Unreal Engine backend are reported as deployment context, not as the
primary scientific endpoint.
\end{abstract}"""

    new_abs = r"""\begin{abstract}
\textbf{Novelty.} We show that a \emph{frozen semantic-family part graph} is a
measurable 3D occupancy prior for lightweight multiview proxy fitting: under an
input-matched, equal-budget comparison, family-conditioned SPPA-MVFit improves
voxel occupancy over a nonsemantic eight-part graph when both fit the same
calibrated top/side silhouettes. The optimizer is deliberately simple; the
knowledge representation (family topology) is the object of inference---not a
new neural reconstructor, not open-set word-to-3D, and not an Unreal systems
demo as the scientific claim.

\textbf{Method.} SPPA-MVFit adjusts five shared parameters of a fixed eight-part
primitive actor with a 31-candidate silhouette objective. Text-only and
silhouette-fitted modes call the same actor builder; only \(\theta\) changes.

\textbf{Evidence.} On a preregistered developer-held-out synthetic test
(\(n{=}240\) actors; six families; CSG-ID and implicit-OOD strata), the primary
paired mean voxel-IoU difference SPPA-MVFit $-$ Generic-MVFit is \(0.190\)
(stratified bootstrap 95\% CI \([0.181,0.199]\)), exceeding the prespecified
\(+0.030\) superiority margin. All twelve family$\times$stratum cells are
positive; OOD stratum mean \(\Delta=0.172\). Median fitter wall time is
\(9.4\)~ms (p95 \(10.6\)~ms) locally.

\textbf{Boundary.} Results are synthetic internal evidence only. Deployment
context (descriptor/update contract, low-polygon runtime proxies) is secondary
and is not used to claim photoreal image-to-3D SOTA, measured flight validity,
or operator benefit.
\end{abstract}"""

    if old_abs not in tex:
        raise SystemExit("abstract block not found")
    tex = tex.replace(old_abs, new_abs)

    # --- After contribution: explicit novelty identification strategy ---
    old_contrib_end = r"""Secondary contributions provide deployment context only:

\begin{itemize}
    \item \textbf{Shared generator contract.} Text-only and silhouette-fitted
    SPPA modes call the same actor builder and part graph; silhouette evidence
    changes only the five-parameter vector \(\theta\).
    \item \textbf{Runtime descriptor/update layer.} \texttt{SPPA-DESC-0.2}/
    \texttt{SPPA-UPD-0.2} separate create from pose/material/shape updates for
    optional Unreal consumption alongside curated assets.
    \item \textbf{Evidence boundary.} Confirmatory occupancy evidence is
    developer-held-out synthetic geometry. Real images in this package are
    qualitative probes without 3D ground truth. Operator benefit, live flight,
    dense VR readiness, and SOTA image-to-3D ranking remain outside the claim.
\end{itemize}"""

    new_contrib_end = r"""Secondary contributions provide deployment context only:

\begin{itemize}
    \item \textbf{Shared generator contract.} Text-only and silhouette-fitted
    SPPA modes call the same actor builder and part graph; silhouette evidence
    changes only the five-parameter vector \(\theta\).
    \item \textbf{Runtime descriptor/update layer.} \texttt{SPPA-DESC-0.2}/
    \texttt{SPPA-UPD-0.2} separate create from pose/material/shape updates for
    optional Unreal consumption alongside curated assets.
    \item \textbf{Evidence boundary.} Confirmatory occupancy evidence is
    developer-held-out synthetic geometry. Real images in this package are
    qualitative probes without 3D ground truth. Operator benefit, live flight,
    dense VR readiness, and SOTA image-to-3D ranking remain outside the claim.
\end{itemize}

\paragraph{Why this is falsifiable novelty.}
Primitive assemblies, visual hulls, and multiview silhouette consistency are
mature~\cite{laurentini1994visualhull,tulsiani2017learning,mo2019partnet,trager2016silhouettes}.
What is new here is the \emph{identification design}: family graph versus
equal-budget generic graph isolates the semantic part prior as a spatial
knowledge representation for lightweight twin proxies. If the family graph did
not help, H1 would fail under the preregistered margin rule. The paper therefore
does not sell a denser mesh, a better neural fitter, or a flight-validated
system; it sells a measured KR effect under a sealed protocol.
"""

    if old_contrib_end not in tex:
        raise SystemExit("contrib end not found")
    tex = tex.replace(old_contrib_end, new_contrib_end)

    # --- Shorten language section opener to reduce dual-claim risk ---
    old_lm = r"""\section{Language Model Use and Geometry Path}
\label{sec:language-geometry-path}

The current SPPA implementation does not call a language model in the runtime
path. The implemented resolver contract records
\texttt{resolver\_source} as a static keyword ontology and marks
\texttt{runtime\_llm\_used} as false; the versioned recipe manifest also
disallows runtime LLM use. The executable system described in this paper should
therefore not be read as a live LLM that answers questions such as ``is this a
mammal?'' or ``how many legs should it have?'' before constructing a
mesh. Those facts are already encoded in reviewed archetype recipes. If an LLM
is used at all, it is only an offline authoring aid that can propose candidate
part decompositions; those candidates must be reviewed, versioned, regression
tested, and admitted before runtime use. The present artifacts record that offline
assistance category, but they do not record a specific LLM provider, model name,
prompt, or output hash, so the paper makes no claim about a particular language
model."""

    new_lm = r"""\section{Language Model Use and Geometry Path}
\label{sec:language-geometry-path}

Runtime SPPA does \emph{not} call a language model. Resolver source is a static
keyword ontology with \texttt{runtime\_llm\_used=false}. Any LLM/ontology tool is
offline authoring only: candidate part recipes must be reviewed, versioned, and
admitted before use. This paper does not claim live LLM anatomy generation or a
specific model/prompt provenance. The scientific endpoint remains family-conditioned
MVFit occupancy (Section~\ref{sec:primary-results}), not language-model geometry."""

    if old_lm not in tex:
        # softer fail: leave LM section if already edited
        print("WARN: LM block not exact; skipping LM compress")
    else:
        tex = tex.replace(old_lm, new_lm)

    # --- Method: identification strategy paragraph ---
    old_method = r"""An actor is an ordered list of eight primitive slots (boxes, cylinders,
ellipsoids). Family graphs and a single \texttt{generic} graph are stored as
static JSON. The only builder used by text-only SPPA, Generic-MVFit, and
SPPA-MVFit is
\begin{equation}
A = \mathrm{Build}(g,\theta),\qquad
\theta=(\log s_x,\log s_y,\log s_z,s_{\mathrm{sec}},o_{\mathrm{sec}}),
\end{equation}
with identical bounds for every graph \(g\). Text-only SPPA uses the family
graph at the default \(\theta_0\). Generic-MVFit and SPPA-MVFit optimize the
same five parameters with the same silhouette disagreement objective and a
fixed 31-candidate local search budget; only the graph identity differs
(\texttt{generic} vs family). Baselines include axis-aligned box, ellipsoid,
capsule, billboard, and nonsemantic visual hull from the same masks."""

    new_method = r"""An actor is an ordered list of eight primitive slots (boxes, cylinders,
ellipsoids). Family graphs and a single \texttt{generic} graph are stored as
static JSON. The only builder used by text-only SPPA, Generic-MVFit, and
SPPA-MVFit is
\begin{equation}
A = \mathrm{Build}(g,\theta),\qquad
\theta=(\log s_x,\log s_y,\log s_z,s_{\mathrm{sec}},o_{\mathrm{sec}}),
\end{equation}
with identical bounds for every graph \(g\). Text-only SPPA uses the family
graph at the default \(\theta_0\). Generic-MVFit and SPPA-MVFit optimize the
same five parameters with the same silhouette disagreement objective and a
fixed 31-candidate local search budget; only the graph identity differs
(\texttt{generic} vs family). This equal-budget construction is the paper's
identification strategy: any occupancy gain is attributed to the family part
prior, not to extra parameters, extra views, or a stronger optimizer.
Baselines include axis-aligned box, ellipsoid, capsule, billboard, and
nonsemantic visual hull~\cite{laurentini1994visualhull} from the same masks."""

    if old_method not in tex:
        raise SystemExit("method block not found")
    tex = tex.replace(old_method, new_method)

    # --- Discussion: journal takeaway ---
    old_disc = r"""The confirmatory result answers the preregistered question: under identical
calibrated silhouettes and optimizer budget, a frozen family part graph improves
lightweight occupancy over a generic eight-part graph by a large and stable
margin. The knowledge representation, not a clever optimizer, is the active
ingredient. Secondary gains over text-only SPPA show that silhouette evidence
helps when the same family graph is held fixed. Gains over boxes, capsules, and
billboards are expected but still quantified under the shared protocol."""

    new_disc = r"""The confirmatory result answers the preregistered question: under identical
calibrated silhouettes and optimizer budget, a frozen family part graph improves
lightweight occupancy over a generic eight-part graph by a large and stable
margin. The knowledge representation, not a clever optimizer, is the active
ingredient. For a geovisualization / spatial digital-twin venue, the transferable
message is that semantic part structure is a spatial prior that can be measured
with occupancy IoU on twin-scale actors, without requiring photoreal reconstruction.
Secondary gains over text-only SPPA show that silhouette evidence helps when the
same family graph is held fixed. Gains over boxes, capsules, and billboards are
expected but still quantified under the shared protocol."""

    if old_disc not in tex:
        print("WARN: discussion lead not found")
    else:
        tex = tex.replace(old_disc, new_disc)

    # --- Conclusion tighten ---
    old_conc = r"""Family-conditioned SPPA-MVFit shows that a reviewed semantic part graph is a
measurable occupancy prior for lightweight multiview proxy fitting. Under a
preregistered equal-budget comparison, SPPA-MVFit improves clean 3D occupancy"""

    new_conc = r"""The novelty of this paper is a sealed, equal-budget demonstration that a
reviewed semantic-family part graph is a measurable occupancy prior for
lightweight multiview proxy fitting. Under a preregistered comparison,
SPPA-MVFit improves clean 3D occupancy"""

    if old_conc not in tex:
        print("WARN: conclusion lead not found")
    else:
        tex = tex.replace(old_conc, new_conc)

    PAPER.write_text(tex, encoding="utf-8")
    print("updated", PAPER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
