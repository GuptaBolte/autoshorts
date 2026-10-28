"""Turns a job JSON into a finished 9:16 MP4: voice, images with slow zoom, captions, music."""
import glob
import json
import os
import random
import subprocess
import sys
import zlib

from . import captions, images, tts

FPS = 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd):
    subprocess.run(cmd, check=True)


def load_channel(name: str) -> dict:
    with open(os.path.join(ROOT, "channels", name, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def ken_burns(img: str, seconds: float, out: str, variant: int):
    frames = max(int(seconds * FPS), 1)
    if variant % 2 == 0:  # slow push in
        z = "min(zoom+0.0007,1.18)"
    else:  # slow pull out
        z = "if(eq(on,0),1.18,max(zoom-0.0007,1.0))"
    vf = (
        f"scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={FPS},format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-vf", vf,
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out])


def pick_music(channel_cfg: dict, job: dict):
    folder = os.path.join(ROOT, channel_cfg.get("music_dir", "assets/music"))
    tracks = sorted(glob.glob(os.path.join(folder, "*.mp3")) + glob.glob(os.path.join(folder, "*.m4a")))
    if not tracks:
        return None
    return random.Random(job.get("id", "")).choice(tracks)


def render(job_path: str, out_dir: str, offline: bool = False) -> str:
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    cfg = load_channel(job["channel"])
    work = os.path.join(out_dir, job["id"])
    os.makedirs(work, exist_ok=True)

    timeline, t, clips, audios = [], 0.0, [], []
    pad = cfg.get("beat_pad_s", 0.25)
    for i, beat in enumerate(job["beats"]):
        # 1) voice for this beat (tts_text lets us feed Devanagari to TTS while captions stay Roman)
        audio = os.path.join(work, f"b{i:02d}.mp3")
        spoken = beat.get("tts_text") or beat["voiceover"]
        if offline:
            tts.silence(beat.get("duration_s", 4), audio)
        else:
            tts.speak(spoken, cfg["voice"], audio, rate=cfg.get("voice_rate", "+0%"), pitch=cfg.get("voice_pitch", "+0Hz"))
        seconds = tts.duration(audio) + pad
        audios.append((audio, seconds))

        # 2) visual for this beat
        img = os.path.join(work, f"b{i:02d}.jpg")
        prompt = f"{beat['visual_prompt']}, {cfg.get('visual_style', '')}".strip(", ")
        seed = zlib.crc32(f"{job['id']}:{i}".encode()) % 100000
        if offline:
            images.fallback(img, i)
        else:
            images.generate(prompt, img, seed=seed, model=cfg.get("image_model", "flux"))
        clip = os.path.join(work, f"b{i:02d}.mp4")
        ken_burns(img, seconds, clip, i)
        clips.append(clip)

        timeline.append({"start": t, "end": t + seconds, "caption": beat.get("caption") or beat["voiceover"],
                         "on_screen_text": beat.get("on_screen_text", "")})
        t += seconds

    # 3) stitch video clips
    vlist = os.path.join(work, "clips.txt")
    with open(vlist, "w") as f:
        f.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    silent = os.path.join(work, "silent.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", vlist, "-c", "copy", silent])

    # 4) stitch voice (each beat padded to its clip length so sync stays exact)
    voice_parts = []
    for i, (a, secs) in enumerate(audios):
        p = os.path.join(work, f"v{i:02d}.wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", a, "-af", f"apad,atrim=0:{secs:.3f}",
             "-ar", "44100", "-ac", "2", p])
        voice_parts.append(p)
    alist = os.path.join(work, "voice.txt")
    with open(alist, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in voice_parts)
    voice = os.path.join(work, "voice.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", voice])

    # 5) music bed under the voice
    music = pick_music(cfg, job)
    mixed = os.path.join(work, "mix.m4a")
    if music:
        vol = cfg.get("music_volume", 0.12)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-stream_loop", "-1", "-i", music,
             "-filter_complex", f"[1:a]volume={vol},afade=t=out:st={max(t - 1.5, 0):.2f}:d=1.5[m];"
                                f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
             "-map", "[a]", "-c:a", "aac", "-b:a", "192k", mixed])
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-c:a", "aac", "-b:a", "192k", mixed])

    # 6) captions burned in, final encode
    ass = captions.build(timeline, os.path.join(work, "subs.ass"), font=cfg.get("caption_font", "DejaVu Sans"))
    final = os.path.join(out_dir, f"{job['id']}.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", mixed,
         "-vf", f"ass={ass}", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", final])
    print(f"[render] {final} ({t:.1f}s)")
    return final


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out", offline="--offline" in sys.argv)
