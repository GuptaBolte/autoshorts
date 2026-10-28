"""Sends talking beats to a free Kaggle GPU (SadTalker) and brings back lip-synced clips.

Secret: KAGGLE_API_TOKEN. Env/var: KAGGLE_USERNAME.
"""
import glob
import json
import os
import shutil
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER = os.environ.get("KAGGLE_USERNAME", "nileshgupta1620")
DATASET = f"{USER}/autoshorts-lipsync-input"
KERNEL = f"{USER}/autoshorts-lipsync"


def available() -> bool:
    return bool(os.environ.get("KAGGLE_API_TOKEN") or os.path.exists(os.path.expanduser("~/.kaggle/access_token")))


def _k(*args, check=True):
    r = subprocess.run(["kaggle", *args], capture_output=True, text=True)
    print(f"[kaggle] {' '.join(args[:3])}: {(r.stdout + r.stderr).strip()[:400]}")
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    return r


def run(portrait: str, audios: dict, work: str, timeout_min: int = 75) -> dict:
    """audios: {beat_name: wav_path}. Returns {beat_name: mp4_path} for the clips that succeeded."""
    ds = os.path.join(work, "kaggle_ds")
    kd = os.path.join(work, "kaggle_kernel")
    out = os.path.join(work, "kaggle_out")
    for d in (ds, kd, out):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)

    shutil.copy(portrait, os.path.join(ds, "portrait" + os.path.splitext(portrait)[1]))
    for name, wav in audios.items():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "16000", "-ac", "1",
                        os.path.join(ds, f"{name}.wav")], check=True)
    json.dump({"title": "autoshorts lipsync input", "id": DATASET, "licenses": [{"name": "CC0-1.0"}]},
              open(os.path.join(ds, "dataset-metadata.json"), "w"))

    # upload inputs (new version if the dataset already exists)
    if _k("datasets", "status", DATASET, check=False).returncode == 0:
        _k("datasets", "version", "-p", ds, "-m", "new job", "--dir-mode", "zip")
    else:
        _k("datasets", "create", "-p", ds)
    for _ in range(30):
        if "ready" in _k("datasets", "status", DATASET, check=False).stdout:
            break
        time.sleep(10)

    shutil.copy(os.path.join(ROOT, "kaggle", "lipsync_kernel.py"), kd)
    json.dump({
        "id": KERNEL, "title": "autoshorts-lipsync", "code_file": "lipsync_kernel.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": True, "enable_internet": True, "dataset_sources": [DATASET],
        "competition_sources": [], "kernel_sources": [],
    }, open(os.path.join(kd, "kernel-metadata.json"), "w"))
    _k("kernels", "push", "-p", kd)

    deadline = time.time() + timeout_min * 60
    time.sleep(60)
    status = ""
    while time.time() < deadline:
        status = _k("kernels", "status", KERNEL, check=False).stdout.lower()
        if "complete" in status or "error" in status or "cancel" in status:
            break
        time.sleep(30)
    _k("kernels", "output", KERNEL, "-p", out, check=False)
    log = glob.glob(os.path.join(out, "*.log"))
    if log:
        print("[kaggle] log tail:\n" + open(log[0], errors="ignore").read()[-3000:])
    found = glob.glob(os.path.join(out, "out", "*.mp4")) + glob.glob(os.path.join(out, "*.mp4"))
    clips = {os.path.splitext(os.path.basename(p))[0]: p for p in found
             if os.path.splitext(os.path.basename(p))[0] in audios}
    print(f"[lipsync] status={status.strip()[:80]} clips={sorted(clips)}")
    return clips
