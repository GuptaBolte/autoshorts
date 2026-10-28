"""Free image generation via Pollinations (no API key), with an offline fallback."""
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

W, H = 1080, 1920


def generate(prompt: str, out_path: str, seed: int = 1, model: str = "flux", retries: int = 3) -> str:
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + f"?width={W}&height={H}&seed={seed}&model={model}&nologo=true&enhance=false"
    )
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "autoshorts/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            Image.open(out_path).verify()  # make sure we got a real image
            _normalize(out_path)
            return out_path
        except Exception as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    print(f"[images] generation failed ({last}); using fallback background")
    return fallback(out_path, seed)


def _normalize(path: str):
    """Crop/resize to exactly 1080x1920 so FFmpeg gets a predictable input."""
    img = Image.open(path).convert("RGB")
    ratio = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * ratio) + 1, int(img.height * ratio) + 1), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img.crop((left, top, left + W, top + H)).save(path, "JPEG", quality=92)


def fallback(out_path: str, seed: int = 1) -> str:
    palettes = [((40, 12, 60), (230, 140, 40)), ((10, 30, 70), (240, 190, 90)), ((60, 10, 20), (250, 170, 60))]
    top, bottom = palettes[seed % len(palettes)]
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    draw.ellipse([W // 2 - 300, H // 2 - 300, W // 2 + 300, H // 2 + 300], outline=(255, 220, 150), width=6)
    img.save(out_path, "JPEG", quality=92)
    return out_path
