"""Image generation. Primary: Cloudflare Workers AI (free tier, no watermark).
Fallback: Pollinations (free, may watermark). Last resort: a plain gradient.

Secrets for Cloudflare: CF_ACCOUNT_ID, CF_API_TOKEN.
"""
import base64
import io
import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
CF_MODELS = os.environ.get(
    "CF_IMAGE_MODELS", "@cf/leonardo/lucid-origin,@cf/black-forest-labs/flux-1-schnell"
).split(",")
NEGATIVE = ("female, woman, feminine face, blue hair, nudity, bare chest, cleavage, deformed hands, extra fingers, "
            "text, watermark, logo, cartoon, disrespectful")


def _post_json(url, payload, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers.get("Content-Type", ""), resp.read()


def _cloudflare(prompt: str, seed: int) -> Image.Image:
    acct, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (acct and token):
        raise RuntimeError("Cloudflare secrets not set")
    last = None
    for model in CF_MODELS:
        model = model.strip()
        if "flux-1-schnell" in model:
            payload = {"prompt": prompt[:2000], "steps": 8}  # square output; framed onto a vertical canvas below
        else:
            payload = {"prompt": prompt, "seed": seed, "width": 1152, "height": 2048,
                       "negative_prompt": NEGATIVE, "num_steps": 30}
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
            for wait in (0, 60, 120):  # free tier has a per-minute rate limit: back off on 429
                if wait:
                    print(f"[images] {model} rate-limited, waiting {wait}s")
                    time.sleep(wait)
                try:
                    ctype, raw = _post_json(url, payload, {"Authorization": f"Bearer {token}"})
                    break
                except urllib.error.HTTPError as err:
                    body = err.read().decode(errors="ignore")[:300]
                    if err.code != 429 or wait == 120 or "daily free allocation" in body:
                        raise RuntimeError(f"HTTP {err.code}: {body}") from None
            if "json" in ctype:
                body = json.loads(raw)
                result = body.get("result", body)
                b64 = result.get("image") if isinstance(result, dict) else None
                if not b64:
                    raise RuntimeError(f"no image in response: {str(body)[:300]}")
                raw = base64.b64decode(b64)
            print(f"[images] cloudflare {model}")
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            last = exc
            print(f"[images] {model} failed: {exc}")
            if "daily free allocation" in str(exc):
                raise RuntimeError("Cloudflare daily free allowance used up (resets 00:00 UTC)") from None
    raise RuntimeError(f"all Cloudflare models failed: {last}")


def _pollinations(prompt: str, seed: int) -> Image.Image:
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
           + f"?width={W}&height={H}&seed={seed}&model=flux&nologo=true")
    headers = {"User-Agent": "autoshorts/1.0"}
    if os.environ.get("POLLINATIONS_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['POLLINATIONS_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")


def _to_vertical(img: Image.Image) -> Image.Image:
    """Fill 1080x1920. Wide/square images sit on a blurred, darkened copy of themselves."""
    if img.height / img.width >= 1.6:
        ratio = max(W / img.width, H / img.height)
        img = img.resize((int(img.width * ratio) + 1, int(img.height * ratio) + 1), Image.LANCZOS)
        left, top = (img.width - W) // 2, (img.height - H) // 2
        return img.crop((left, top, left + W, top + H))
    bg = img.resize((H, H), Image.LANCZOS).crop(((H - W) // 2, 0, (H - W) // 2 + W, H))
    bg = bg.filter(ImageFilter.GaussianBlur(40)).point(lambda p: int(p * 0.55))
    fg = img.resize((W, int(img.height * W / img.width)), Image.LANCZOS)
    bg.paste(fg, (0, (H - fg.height) // 2))
    return bg


def generate(prompt: str, out_path: str, seed: int = 1, model: str = "flux", retries: int = 2) -> str:
    for provider in (_cloudflare, _pollinations):
        for attempt in range(retries):
            try:
                _to_vertical(provider(prompt, seed)).save(out_path, "JPEG", quality=94)
                return out_path
            except Exception as exc:
                print(f"[images] {provider.__name__} attempt {attempt + 1} failed: {exc}")
                if "secrets not set" in str(exc) or "allowance used up" in str(exc) or "402" in str(exc):
                    break
                time.sleep(4 * (attempt + 1))
    print("[images] all providers failed; using fallback background")
    return fallback(out_path, seed)


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
