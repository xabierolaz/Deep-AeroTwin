# -*- coding: utf-8 -*-
"""Aggregate the 20260722 generator gallery run into JSON + MD summaries.

Parses the per-method stdout logs of the run, merges the reused 20260721
tower/tractor TripoSR + Hunyuan results (same inputs, same 6 GB cap), and
attaches the qualitative fidelity notes assigned after visual render review.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test")
RUN = ROOT / "experiments/sppa_sota_benchmark/runs/20260722_generator_gallery"
RESULTS = ROOT / "papers/semantic_proxy_3d/benchmarks/results"

CASES = ["tower", "tractor", "biker", "cow", "car", "tractor_trailer"]
METHOD_ORDER = ["triposr_warm_r128_6gb", "shap_e_image_k64_6gb", "point_e_image_sdf32_6gb", "hunyuan3d_2mini_turbo_rgba_6gb"]

INPUTS = {
    "tower": "experiments/sppa_sota_benchmark/inputs/tower_real_flight_crop_512.png",
    "tractor": "experiments/sppa_sota_benchmark/inputs/tractor_real_flight_crop_512.png",
    "biker": "experiments/sppa_sota_benchmark/inputs/biker_real_road_crop_512.png",
    "cow": "experiments/sppa_sota_benchmark/inputs/cow.png",
    "car": "experiments/sppa_sota_benchmark/inputs/car.png",
    "tractor_trailer": "experiments/sppa_sota_benchmark/inputs/tractor_trailer_real_mountain_crop_512.png",
}

# Reused from runs/20260721_real_flight_sppa_triposr_hunyuan (same inputs, same
# warm r128 + 6 GB torch-allocator cap; see benchmarks/results/real_flight_comparison_20260721.json)
REUSED_20260721 = {
    ("tower", "triposr_warm_r128_6gb"): {
        "status": "ok", "triangles": 26836, "inference_sec": 0.489, "wall_sec": 1.219,
        "peak_vram_mb": 1868, "source": "reused_20260721",
        "qualitative": "amorphous textured blob, no tower structure",
    },
    ("tractor", "triposr_warm_r128_6gb"): {
        "status": "ok", "triangles": 39700, "inference_sec": 0.092, "wall_sec": 0.475,
        "peak_vram_mb": 1870, "source": "reused_20260721",
        "qualitative": "amorphous textured blob, no tractor structure",
    },
    ("tower", "hunyuan3d_2mini_turbo_rgba_6gb"): {
        "status": "hard_failure", "error": "No surface found (5 and 20 inference steps)",
        "wall_sec": 2.48, "peak_vram_mb": 4552, "source": "reused_20260721",
        "qualitative": "no mesh produced (aerial crop failure mode)",
    },
    ("tractor", "hunyuan3d_2mini_turbo_rgba_6gb"): {
        "status": "hard_failure", "error": "No surface found",
        "wall_sec": 1.31, "peak_vram_mb": 4552, "source": "reused_20260721",
        "qualitative": "no mesh produced (aerial crop failure mode)",
    },
}

QUALITATIVE = {
    ("tower", "shap_e_image_k64_6gb"): "dark boxy mass, no pylon structure (aerial input)",
    ("tower", "point_e_image_sdf32_6gb"): "failure: degenerate SDF mesh (8 tris sliver)",
    ("tractor", "shap_e_image_k64_6gb"): "partially recognizable: green mass with four wheel blobs (tractor colors)",
    ("tractor", "point_e_image_sdf32_6gb"): "partial: hollow green frame shell, tractor colors, broken geometry",
    ("biker", "triposr_warm_r128_6gb"): "amorphous textured blob, no rider/bicycle structure",
    ("biker", "shap_e_image_k64_6gb"): "dark boxy blob, no rider/bicycle structure",
    ("biker", "point_e_image_sdf32_6gb"): "failure: scattered thin fragments (2.5k tris)",
    ("biker", "hunyuan3d_2mini_turbo_rgba_6gb"): "failure: degenerate flat slab (2x2 m x 1 cm pancake)",
    ("cow", "triposr_warm_r128_6gb"): "amorphous textured blob, no cow structure",
    ("cow", "shap_e_image_k64_6gb"): "failure: thin disconnected slivers (12k tris)",
    ("cow", "point_e_image_sdf32_6gb"): "failure: sparse specks (492 tris)",
    ("cow", "hunyuan3d_2mini_turbo_rgba_6gb"): "recognizable quadruped (cow-like body, head, legs)",
    ("car", "triposr_warm_r128_6gb"): "rounded red-tinted mound, faint car hint, no structure",
    ("car", "shap_e_image_k64_6gb"): "recognizable red car (body, hood, wheels)",
    ("car", "point_e_image_sdf32_6gb"): "recognizable red car (low-res but coherent)",
    ("car", "hunyuan3d_2mini_turbo_rgba_6gb"): "no mesh produced: 'No surface found' at 5 and 20 steps",
    ("tractor_trailer", "triposr_warm_r128_6gb"): "amorphous textured blob, no vehicle structure",
    ("tractor_trailer", "shap_e_image_k64_6gb"): "gray slab/arch mass, not recognizable",
    ("tractor_trailer", "point_e_image_sdf32_6gb"): "partial: frame shell + slab, not coherent",
    ("tractor_trailer", "hunyuan3d_2mini_turbo_rgba_6gb"): "partially recognizable blocky vehicle mass",
}

LOG_BY_METHOD = {
    "triposr_warm_r128_6gb": "triposr.stdout.log",
    "shap_e_image_k64_6gb": "shape_image.stdout.log",
    "point_e_image_sdf32_6gb": "pointe_image.stdout.log",
    "hunyuan3d_2mini_turbo_rgba_6gb": "hunyuan.stdout.log",
}


def parse_log(path: Path) -> dict:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "SPPA_BENCH_OBJECT " not in line:
            continue
        payload = json.loads(line.split("SPPA_BENCH_OBJECT ", 1)[1])
        rows[payload["label"]] = payload
    return rows


def normalize(method: str, label: str, p: dict) -> dict:
    row = {"status": p["status"]}
    if p["status"] == "ok":
        row["triangles"] = p.get("triangles")
        if method == "triposr_warm_r128_6gb":
            row["inference_sec"] = round(p["inference_sec"], 3)
        elif method == "shap_e_image_k64_6gb":
            row["inference_sec"] = round(p["sample_sec"], 3)
            row["decode_sec"] = round(p["decode_sec"], 3)
        elif method == "point_e_image_sdf32_6gb":
            row["inference_sec"] = round(p["pointcloud_sec"], 3)
            row["mesh_sec"] = round(p.get("mesh_sec", 0.0), 3)
        elif method == "hunyuan3d_2mini_turbo_rgba_6gb":
            row["inference_sec"] = round(p["generation_sec"], 3)
        row["wall_sec"] = round(p["wall_sec"], 3)
        row["peak_vram_mb"] = round(p.get("torch_peak_allocated_mb", 0.0), 1)
        row["mesh_path"] = p.get("mesh_path")
        render = RUN / "outputs" / method / label / f"{label}_render.png"
        if render.exists():
            row["render_path"] = str(render.relative_to(ROOT)).replace("\\", "/")
    else:
        row["error"] = p.get("error", "")
        row["wall_sec"] = round(p.get("wall_sec", 0.0), 3)
        row["peak_vram_mb"] = round(p.get("torch_peak_allocated_mb", 0.0), 1)
    return row


def main() -> None:
    gallery = {}
    for case in CASES:
        gallery[case] = {"input": INPUTS[case], "methods": {}}

    for method in METHOD_ORDER:
        rows = parse_log(RUN / LOG_BY_METHOD[method])
        for case in CASES:
            key = (case, method)
            if key in REUSED_20260721:
                entry = dict(REUSED_20260721[key])
                render = RUN / "outputs" / method / case / f"{case}_render.png"
                if render.exists():
                    entry["render_path"] = str(render.relative_to(ROOT)).replace("\\", "/")
                mesh = RUN / "outputs" / method / case / f"{case}.obj"
                if mesh.exists():
                    entry["mesh_path"] = str(mesh.relative_to(ROOT)).replace("\\", "/")
                gallery[case]["methods"][method] = entry
            elif case in rows:
                entry = normalize(method, case, rows[case])
                entry["source"] = "20260722_generator_gallery"
                if key in QUALITATIVE:
                    entry["qualitative"] = QUALITATIVE[key]
                gallery[case]["methods"][method] = entry
            else:
                gallery[case]["methods"][method] = {"status": "not_run"}

    # carry qualitative notes onto reused rows too
    for (case, method), note in QUALITATIVE.items():
        gallery[case]["methods"][method].setdefault("qualitative", note)

    doc = {
        "schema": "SPPA-GENERATOR-GALLERY-0.1",
        "created_utc": "2026-07-22T00:00:00Z",
        "run_dir": "experiments/sppa_sota_benchmark/runs/20260722_generator_gallery",
        "hardware": "NVIDIA GeForce RTX 5090 32 GB, driver 610.62",
        "conventions": {
            "vram_cap": "6 GB torch-allocator cap (torch.cuda.set_per_process_memory_fraction), same as 20260703/20260721 waves",
            "triposr": "warm load, mc_resolution=128, chunk_size=4096, OBJ export",
            "shap_e": "image300M + transmitter, Karras 64 steps, guidance 3.0, fp16, STF mesh decode",
            "point_e": "base40M image-cond + upsample40M (1024->4096 pts) + SDF grid 32, guidance 3.0",
            "hunyuan": "Hunyuan3D-2mini turbo subfolder, 5 steps (car retried with 20), octree 380, FlashVDM, GLB export",
            "renders": "software painter's algorithm, fixed camera az=35 el=25, white background, isotropic fit, vertex colors when present",
        },
        "reused_results": "tower/tractor TripoSR and Hunyuan rows reused from runs/20260721_real_flight_sppa_triposr_hunyuan (identical inputs and config)",
        "claim_boundary": "No 3D ground truth exists for the real photos; fidelity column is qualitative render review only. car/cow inputs are synthetic proxy crops, not real detector outputs (see inputs/input_provenance.json).",
        "cases": gallery,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS / "generator_gallery_20260722.json"
    json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # ---- markdown
    lines = []
    lines.append("# Generator gallery — image-to-3D on all available real/proxy inputs (2026-07-22)")
    lines.append("")
    lines.append("Run dir: `experiments/sppa_sota_benchmark/runs/20260722_generator_gallery/`. "
                 "All neural generators measured on the same RTX 5090 under the 6 GB torch-allocator cap. "
                 "tower/tractor TripoSR and Hunyuan rows reused from the 20260721 wave (same inputs/config).")
    lines.append("")
    lines.append("| case | method | status | triangles | inference (s) | wall (s) | peak VRAM (MB) | qualitative |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case in CASES:
        for method in METHOD_ORDER:
            m = gallery[case]["methods"][method]
            name = method.replace("_6gb", "")
            if m["status"] == "ok":
                lines.append(
                    f"| {case} | {name} | ok | {m['triangles']} | {m.get('inference_sec','-')} | {m['wall_sec']} | {m['peak_vram_mb']} | {m.get('qualitative','')} |"
                )
            elif m["status"] == "not_run":
                lines.append(f"| {case} | {name} | not run | - | - | - | - | |")
            else:
                note = m.get("error", "")
                if m.get("qualitative"):
                    note = f"{note} — {m['qualitative']}" if note else m["qualitative"]
                lines.append(
                    f"| {case} | {name} | {m['status']} | - | - | {m.get('wall_sec','-')} | {m.get('peak_vram_mb','-')} | {note} |"
                )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Inputs**: tower/tractor are real flight-photo crops (aerial, 2026-07-21); biker is a real road photo; "
                 "tractor_trailer is a real mountain photo; cow/car are synthetic proxy crops (`inputs/input_provenance.json`).")
    lines.append("- **Hunyuan3D-2mini-turbo**: confirmed view-dependent failure. Aerial crops (tower/tractor) and the synthetic "
                 "car crop fail with `No surface found` (car retried with 20 steps, same failure); biker produces a degenerate "
                 "flat slab; cow is a recognizable quadruped; tractor_trailer a blocky vehicle mass.")
    lines.append("- **TripoSR**: produces amorphous textured blobs on all six inputs (fast, <1 s, ~1.9 GB).")
    lines.append("- **Shap-E image**: best on ground-level synthetic car (recognizable); tractor partially recognizable; "
                 "aerial and low-texture inputs collapse to boxy masses or slivers.")
    lines.append("- **Point-E image (base40M + SDF32)**: only the synthetic car is recognizable; tower/cow/biker fail with "
                 "degenerate or fragmented SDF meshes; tractor/tractor_trailer yield hollow frame shells.")
    lines.append("- Renders: `outputs/<method>/<case>/<case>_render.png` (fixed camera, white background); "
                 "contact sheet: `runs/20260722_generator_gallery/contact_sheet.png`.")
    lines.append("- nvidia-smi was unavailable in the run shells (exit 255); VRAM peaks are torch allocator peaks "
                 "(`torch_peak_allocated_mb`), consistent with the July waves.")
    md_path = RESULTS / "generator_gallery_20260722.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
