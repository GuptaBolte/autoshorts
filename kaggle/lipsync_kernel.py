"""Runs on a free Kaggle GPU. Makes the Krishna portrait speak each audio file with SadTalker.

Kaggle's default Python is too new for SadTalker's dependencies, so this builds an isolated
Python 3.10 environment (with uv) using the versions SadTalker was tested on.

Input dataset: portrait image + one .wav per talking beat.
Output: /kaggle/working/out/<beat>.mp4
"""
import glob
import os
import shutil
import subprocess
import sys

IN = "/kaggle/input"  # dataset mount layout varies, so search it recursively
WORK = "/kaggle/working"
OUT = f"{WORK}/out"
ST = "/tmp/SadTalker"          # outside /kaggle/working so it never lands in the output
VENV = "/tmp/venv"
PY = f"{VENV}/bin/python"
os.makedirs(OUT, exist_ok=True)


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


uvpip = f"uv pip install --python {PY} -q"
sh("pip install -q uv")
sh(f"uv venv {VENV} --python 3.10")
sh(f"{uvpip} torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118")
sh(f"{uvpip} \"setuptools<70\" wheel numpy==1.23.5 cython")  # newer setuptools dropped pkg_resources
sh(f"{uvpip} --no-build-isolation basicsr==1.4.2")
sh(f"{uvpip} face_alignment==1.3.5 imageio==2.19.3 imageio-ffmpeg==0.4.7 librosa==0.9.2 numba resampy==0.3.1 "
   f"pydub==0.25.1 scipy==1.10.1 kornia==0.6.8 tqdm yacs==0.1.8 pyyaml joblib==1.1.0 scikit-image==0.19.3 "
   f"facexlib==0.3.0 gfpgan==1.3.8 av safetensors opencv-python==4.8.1.78")

sh(f"git clone --depth 1 https://github.com/OpenTalker/SadTalker {ST}")
os.chdir(ST)
sh("bash scripts/download_models.sh")

sh(f"find {IN} -maxdepth 6 | head -50")
files = glob.glob(f"{IN}/**/*", recursive=True)
portrait = next(p for p in files if p.lower().endswith((".jpg", ".jpeg", ".png")))
wavs = sorted(p for p in files if p.lower().endswith(".wav"))
print("portrait:", portrait, "wavs:", wavs, flush=True)
failed = []
for wav in wavs:
    name = os.path.splitext(os.path.basename(wav))[0]
    res = f"/tmp/res/{name}"
    try:
        sh(f"{PY} inference.py --driven_audio '{wav}' --source_image '{portrait}' --result_dir '{res}' "
           f"--still --preprocess full --enhancer gfpgan --size 512 --expression_scale 1.0")
        vids = sorted(glob.glob(f"{res}/**/*.mp4", recursive=True), key=os.path.getmtime)
        final = [v for v in vids if "enhanced" in v] or vids
        shutil.copy(final[-1], f"{OUT}/{name}.mp4")
        print(f"OK {name}", flush=True)
    except Exception as exc:
        failed.append(name)
        print(f"FAILED {name}: {exc}", flush=True)

print("done; failed:", failed)
sys.exit(1 if wavs and len(failed) == len(wavs) else 0)
