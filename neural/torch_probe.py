import torch, time
print('torch', torch.__version__, 'cuda', torch.version.cuda, 'avail', torch.cuda.is_available())
if torch.cuda.is_available():
    print('dev', torch.cuda.get_device_name(0), 'cap', torch.cuda.get_device_capability(0))
    print('arch_list', torch.cuda.get_arch_list())
    a = torch.randn(4096, 4096, device='cuda')
    b = torch.randn(4096, 4096, device='cuda')
    torch.cuda.synchronize(); t = time.time()
    for _ in range(50):
        c = a @ b
    torch.cuda.synchronize()
    print('matmul ms/iter', round((time.time() - t) / 50 * 1000, 3))
    print('PROBE_OK')
