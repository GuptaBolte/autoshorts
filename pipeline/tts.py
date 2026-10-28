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


# Voice presets applied after TTS. "divine": ~2 semitones deeper, warm low end, a faint octave-down
# layer for weight, and a temple-hall reverb tail. Tempo is preserved (atempo undoes the asetrate speed-up).
VOICE_FX = {
    "divine": (
        "[0:a]aresample=48000,asetrate=48000*0.89,aresample=48000,atempo=1.1236,"
        "bass=g=5:f=120:w=0.6,treble=g=-2,equalizer=f=3200:t=q:w=1.2:g=-2,asplit=2[main][sub];"
        "[sub]asetrate=48000*0.5,aresample=48000,atempo=2.0,lowpass=f=400,volume=0.22[low];"
        "[main][low]amix=inputs=2:duration=first:normalize=0,"
        "aecho=0.85:0.55:45|85|130:0.28|0.18|0.10,"
        "acompressor=threshold=0.12:ratio=3:attack=10:release=200,loudnorm=I=-15:TP=-1.5:LRA=9"
    ),
    "none": "[0:a]aresample=48000,loudnorm=I=-15:TP=-1.5",
}


def apply_fx(in_path: str, out_path: str, preset: str = "divine") -> str:
    graph = VOICE_FX.get(preset, VOICE_FX["none"])
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-filter_complex", graph + "[out]",
         "-map", "[out]", "-ac", "2", "-c:a", "pcm_s16le", out_path],
        check=True,
    )
    return out_path


def drone(seconds: float, out_path: str, sa_hz: float = 146.83) -> str:
    """Soft tanpura-style drone (Sa-Pa-Sa') used when no flute/music track is supplied."""
    pa, hi, lo = sa_hz * 1.5, sa_hz * 2, sa_hz / 2
    swell = lambda ph: f"(0.6+0.4*sin(2*PI*0.18*t+{ph}))"
    expr = "+".join([
        f"0.16*sin(2*PI*{sa_hz}*t)*{swell(0)}", f"0.05*sin(2*PI*{sa_hz*3}*t)*{swell(0.7)}",
        f"0.11*sin(2*PI*{pa}*t)*{swell(1.6)}", f"0.04*sin(2*PI*{pa*2}*t)*{swell(2.2)}",
        f"0.09*sin(2*PI*{hi}*t)*{swell(3.1)}", f"0.13*sin(2*PI*{lo}*t)",
    ])
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d={seconds:.2f}",
         "-af", "lowpass=f=1600,aecho=0.8:0.7:120|240:0.35|0.2,afade=t=in:d=2,volume=0.9",
         "-ac", "2", "-c:a", "pcm_s16le", out_path],
        check=True,
    )
    return out_path


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
