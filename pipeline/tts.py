"""Text-to-speech with Microsoft Edge neural voices (free, no API key)."""
import asyncio
import subprocess


async def _speak(text: str, voice: str, rate: str, pitch: str, out_path: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def speak(text: str, voice: str, out_path: str, rate: str = "+0%", pitch: str = "+0Hz", retries: int = 3):
    last = None
    for _ in range(retries):
        try:
            asyncio.run(_speak(text, voice, rate, pitch, out_path))
            return out_path
        except Exception as exc:  # network hiccups are common, retry
            last = exc
    raise RuntimeError(f"TTS failed after {retries} tries: {last}")


def silence(seconds: float, out_path: str):
    """Fallback used only in offline tests, when TTS is unreachable."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", out_path],
        check=True,
    )
    return out_path


def duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())
