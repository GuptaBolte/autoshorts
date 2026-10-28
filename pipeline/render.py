"""Turns a job JSON into finished vertical videos: a 4K master (YouTube) and a 1080p copy (Instagram).

Per beat: TTS -> voice FX -> image (generated, AI-upscaled to 4K) -> slow zoom clip.
Then: stitch, ambient bed (flute track if supplied, else tanpura drone), burn captions.
"""
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import zlib

from . import captions, images, lipsync, tts, upscale

FPS = 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd):
    subprocess.run(cmd, check=True)


def load_channel(name: str) -> dict:
    with open(os.path.join(ROOT, "channels", name, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def motion_clip(img: str, seconds: float, out: str, variant: int, w: int, h: int, zoom: float = 0.10):
    """Smooth slow push-in / pull-out. scale+crop per frame avoids zoompan's integer-pixel jitter."""
    frames = max(int(round(seconds * FPS)), 1)
    k = f"(1+{zoom}*t/{seconds:.3f})" if variant % 2 == 0 else f"(1+{zoom}-{zoom}*t/{seconds:.3f})"
    vf = (
        f"scale=w='trunc({w}*{k}/2)*2':h='trunc({h}*{k}/2)*2':eval=frame:flags=bicubic,"
        f"crop={w}:{h}:(iw-{w})/2:(ih-{h})/2,setsar=1,format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", img, "-vf", vf,
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out])


def talking_clip(src: str, seconds: float, out: str, w: int, h: int):
    """Fit a lip-sync clip to the frame (cover-crop), very slow push-in, hold the last frame to the beat length."""
    frames = max(int(round(seconds * FPS)), 1)
    vf = (
        f"fps={FPS},scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},"
        f"tpad=stop_mode=clone:stop_duration=5,"
        f"scale=w='trunc({w}*(1+0.04*t/{seconds:.3f})/2)*2':h='trunc({h}*(1+0.04*t/{seconds:.3f})/2)*2':eval=frame,"
        f"crop={w}:{h}:(iw-{w})/2:(ih-{h})/2,setsar=1,format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", vf, "-an", "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out])


def ambient_bed(cfg: dict, job: dict, seconds: float, work: str):
    folder = os.path.join(ROOT, cfg.get("music_dir", "assets/music"))
    tracks = sorted(glob.glob(os.path.join(folder, "*.mp3")) + glob.glob(os.path.join(folder, "*.m4a"))
                    + glob.glob(os.path.join(folder, "*.wav")))
    if tracks:
        return random.Random(job.get("id", "")).choice(tracks), cfg.get("music_volume", 0.14)
    if cfg.get("ambient_fallback") == "drone":
        return tts.drone(seconds + 1, os.path.join(work, "drone.wav"), cfg.get("drone_sa_hz", 146.83)), \
            cfg.get("drone_volume", 0.10)
    return None, 0


def visual_prompt(beat: dict, cfg: dict) -> str:
    prompt = beat["visual_prompt"]
    for key, desc in cfg.get("characters", {}).items():
        prompt = prompt.replace("{" + key + "}", desc)
    return f"{prompt}, {cfg.get('visual_style', '')}".strip(", ")


def render(job_path: str, out_dir: str, offline: bool = False) -> dict:
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    cfg = load_channel(job["channel"])
    W, H = cfg.get("resolution", [2160, 3840])
    work = os.path.join(out_dir, job["id"])
    os.makedirs(work, exist_ok=True)

    timeline, t, clips, voices = [], 0.0, [], []
    pad = cfg.get("beat_pad_s", 0.35)
    for i, beat in enumerate(job["beats"]):
        # 1) voice (tts_text lets Devanagari drive TTS while captions stay in Roman Hinglish)
        raw = os.path.join(work, f"b{i:02d}.mp3")
        text = beat.get("tts_text") or beat["voiceover"]
        fx = cfg.get("voice_fx", "none")
        if offline:
            tts.silence(beat.get("duration_s", 4), raw)
        else:
            spoken = False
            g = cfg.get("gemini_tts")
            if g and os.environ.get("GEMINI_API_KEY"):
                try:
                    tts.gemini_speak(text, raw, voice=g.get("voice", "Charon"), style=g.get("style", ""),
                                     model=g.get("model", "gemini-2.5-flash-preview-tts"))
                    fx, spoken = g.get("voice_fx", "divine_natural"), True
                except Exception as exc:
                    print(f"[tts] Gemini failed, falling back to edge-tts: {exc}")
            if not spoken:
                tts.speak(text, cfg["voice"], raw, rate=cfg.get("voice_rate", "+0%"), pitch=cfg.get("voice_pitch", "+0Hz"))
        voice = tts.apply_fx(raw, os.path.join(work, f"v{i:02d}.wav"), fx)
        seconds = tts.duration(voice) + pad
        voices.append((voice, seconds))

    # 2) talking beats: Krishna's fixed portrait lip-synced on a free Kaggle GPU
    talking = {}
    portrait = os.path.join(ROOT, cfg.get("portrait", ""))
    want = {f"b{i:02d}": voices[i][0] for i, b in enumerate(job["beats"]) if b.get("talking")}
    if want and not offline and cfg.get("portrait") and os.path.exists(portrait) and lipsync.available():
        try:
            talking = lipsync.run(portrait, want, work)
        except Exception as exc:
            print(f"[lipsync] failed, using still images instead: {exc}")

    # 3) visuals per beat
    for i, beat in enumerate(job["beats"]):
        seconds = voices[i][1]
        clip = os.path.join(work, f"b{i:02d}.mp4")
        name = f"b{i:02d}"
        if name in talking:
            talking_clip(talking[name], seconds, clip, W, H)
        else:
            img = os.path.join(work, f"b{i:02d}.jpg")
            if offline:
                images.fallback(img, i)
            elif beat.get("talking") and os.path.exists(portrait):
                shutil.copy(portrait, img)  # keep Krishna's face consistent even without lip-sync
            else:
                images.generate(visual_prompt(beat, cfg), img, seed=zlib.crc32(f"{job['id']}:{i}".encode()) % 100000,
                                model=cfg.get("image_model", "flux"))
            upscale.to_size(img, W, H, use_ai=cfg.get("ai_upscale", True))
            motion_clip(img, seconds, clip, i, W, H)
        clips.append(clip)

        timeline.append({"start": t, "end": t + seconds, "caption": beat.get("caption") or beat["voiceover"],
                         "on_screen_text": beat.get("on_screen_text", "")})
        t += seconds

    # 3) stitch video
    vlist = os.path.join(work, "clips.txt")
    with open(vlist, "w") as f:
        f.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    silent = os.path.join(work, "silent.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", vlist, "-c", "copy", silent])

    # 4) stitch voice, each beat padded/trimmed to its clip length so sync is exact
    parts = []
    for i, (v, secs) in enumerate(voices):
        p = os.path.join(work, f"p{i:02d}.wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", v, "-af", f"apad,atrim=0:{secs:.3f}", "-ar", "48000", "-ac", "2", p])
        parts.append(p)
    alist = os.path.join(work, "voice.txt")
    with open(alist, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    voice = os.path.join(work, "voice.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", voice])

    # 5) ambient bed under the voice, ducked slightly while Krishna speaks
    bed, vol = ambient_bed(cfg, job, t, work)
    mixed = os.path.join(work, "mix.m4a")
    if bed:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-stream_loop", "-1", "-i", bed, "-filter_complex",
             f"[1:a]aresample=48000,volume={vol},afade=t=out:st={max(t - 2, 0):.2f}:d=2[m];"
             f"[m][0:a]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=400[md];"
             f"[0:a][md]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "[a]", "-c:a", "aac", "-b:a", "256k", mixed])
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-c:a", "aac", "-b:a", "256k", mixed])

    # 6) captions + final encodes
    ass = captions.build(timeline, os.path.join(work, "subs.ass"), font=cfg.get("caption_font", "DejaVu Sans"))
    master = os.path.join(out_dir, f"{job['id']}_4k.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", mixed, "-vf", f"ass={ass}",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", cfg.get("x264_preset", "veryfast"),
         "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", master])
    reel = os.path.join(out_dir, f"{job['id']}_1080.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", master, "-vf", "scale=1080:1920:flags=lanczos",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "20M", "-bufsize", "40M",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", reel])
    print(f"[render] {master} + {reel} ({t:.1f}s)")
    return {"youtube": master, "instagram": reel, "seconds": round(t, 1)}


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out", offline="--offline" in sys.argv)
