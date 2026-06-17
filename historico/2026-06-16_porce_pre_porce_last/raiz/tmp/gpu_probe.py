import json, subprocess, sys
out = {}
try:
    import torch
    out["torch"] = torch.__version__
    out["cuda_available"] = torch.cuda.is_available()
    out["torch_cuda"] = torch.version.cuda
    if torch.cuda.is_available():
        out["device"] = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        out["capability"] = f"sm_{cap[0]}{cap[1]}"
        out["arch_list"] = torch.cuda.get_arch_list()
        # quick matmul to confirm kernels run on this arch
        try:
            a = torch.randn(2048, 2048, device="cuda")
            b = torch.randn(2048, 2048, device="cuda")
            c = (a @ b).sum().item()
            out["matmul_ok"] = True
        except Exception as e:
            out["matmul_ok"] = False
            out["matmul_err"] = str(e)[:300]
except Exception as e:
    out["torch_error"] = str(e)[:300]
open(r"D:\Deep-AeroTwin-UE57-Test\tmp\gpu_probe.json", "w").write(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
