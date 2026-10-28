"""AI upscaling to 4K with Real-ESRGAN's compact model (realesr-general-x4v3), CPU-friendly.

Only needs torch. Weights (~5 MB) download once from the official Real-ESRGAN GitHub release.
Falls back to high-quality Lanczos + sharpening if torch or the weights are unavailable.
"""
import os
import urllib.request

from PIL import Image, ImageFilter

WEIGHTS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = os.path.join(ROOT, "models", "realesr-general-x4v3.pth")
_model = None


def _build():
    import torch
    from torch import nn

    class SRVGGNetCompact(nn.Module):
        def __init__(self, feat=64, convs=32, scale=4):
            super().__init__()
            self.scale = scale
            body = [nn.Conv2d(3, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
            for _ in range(convs):
                body += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
            body += [nn.Conv2d(feat, 3 * scale * scale, 3, 1, 1)]
            self.body = nn.ModuleList(body)
            self.up = nn.PixelShuffle(scale)

        def forward(self, x):
            out = x
            for layer in self.body:
                out = layer(out)
            out = self.up(out)
            return out + nn.functional.interpolate(x, scale_factor=self.scale, mode="nearest")

    if not os.path.exists(WEIGHTS):
        os.makedirs(os.path.dirname(WEIGHTS), exist_ok=True)
        urllib.request.urlretrieve(WEIGHTS_URL, WEIGHTS)
    net = SRVGGNetCompact()
    state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
    net.load_state_dict(state.get("params", state))
    net.eval()
    torch.set_num_threads(max(os.cpu_count() or 2, 2))
    return net


def _ai_upscale(img: Image.Image, tile: int = 256, pad: int = 12) -> Image.Image:
    """x4 upscale in tiles so memory stays small on free CI runners."""
    global _model
    import numpy as np
    import torch

    if _model is None:
        _model = _build()
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = arr.shape
    out = np.zeros((h * 4, w * 4, 3), dtype=np.float32)
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(y - pad, 0), max(x - pad, 0)
                y1, x1 = min(y + tile + pad, h), min(x + tile + pad, w)
                t = torch.from_numpy(arr[y0:y1, x0:x1].transpose(2, 0, 1)).unsqueeze(0)
                r = _model(t).squeeze(0).clamp(0, 1).numpy().transpose(1, 2, 0)
                ty, tx = (y - y0) * 4, (x - x0) * 4
                th, tw = min(tile, h - y) * 4, min(tile, w - x) * 4
                out[y * 4:y * 4 + th, x * 4:x * 4 + tw] = r[ty:ty + th, tx:tx + tw]
    return Image.fromarray((out * 255.0).round().astype("uint8"))


def to_size(path: str, width: int, height: int, use_ai: bool = True) -> str:
    img = Image.open(path).convert("RGB")
    if img.width >= width and img.height >= height:
        return path
    if use_ai:
        try:
            # feed at most half the target size: x4 then downsample keeps all source detail, sharper than plain x2
            src = img.resize((width // 2, height // 2), Image.LANCZOS) if img.width > width // 2 else img
            big = _ai_upscale(src)
            big.resize((width, height), Image.LANCZOS).save(path, "JPEG", quality=95)
            return path
        except Exception as exc:
            print(f"[upscale] AI upscale unavailable ({exc}); using Lanczos")
    img = img.resize((width, height), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    img.save(path, "JPEG", quality=95)
    return path
