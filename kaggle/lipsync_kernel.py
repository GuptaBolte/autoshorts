"""Runs on a free Kaggle GPU. Makes the Krishna portrait speak each audio file with SadTalker.

Input dataset: portrait.jpg + one .wav per talking beat.
Output: /kaggle/working/out/<beat>.mp4 (the runner downloads these).
"""
import glob
import os
import shutil
import subprocess
import sys

IN = sorted(glob.glob("/kaggle/input/*"))[0]
OUT = "/kaggle/working/out"
ST = "/kaggle/working/SadTalker"
os.makedirs(OUT, exist_ok=True)


def sh(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def patch(path, old, new):
    p = os.path.join(ST, path)
    if os.path.exists(p):
        s = open(p).read()
        if old in s:
            open(p, "w").write(s.replace(old, new))
            print(f"patched {path}")


sh(f"git clone --depth 1 https://github.com/OpenTalker/SadTalker {ST}")
sh("pip install -q face_alignment==1.3.5 imageio==2.31.1 imageio-ffmpeg librosa==0.10.1 resampy pydub "
   "scipy kornia yacs pyyaml joblib scikit-image basicsr==1.4.2 facexlib gfpgan av safetensors")

# compatibility fixes for current torch/numpy on Kaggle
import basicsr  # noqa: E402

deg = os.path.join(os.path.dirname(basicsr.__file__), "data", "degradations.py")
s = open(deg).read().replace("torchvision.transforms.functional_tensor", "torchvision.transforms.functional")
open(deg, "w").write(s)
patch("src/face3d/util/preprocess.py", "np.array([w0, h0, s, t[0], t[1]])",
      "np.array([w0, h0, s, float(t[0]), float(t[1])])")
for f in glob.glob(f"{ST}/src/**/*.py", recursive=True):
    txt = open(f).read()
    if "np.float)" in txt or "np.float," in txt:
        open(f, "w").write(txt.replace("np.float)", "np.float64)").replace("np.float,", "np.float64,"))

os.chdir(ST)
sh("bash scripts/download_models.sh")

portrait = next(p for p in glob.glob(f"{IN}/*") if p.lower().endswith((".jpg", ".jpeg", ".png")))
failed = []
for wav in sorted(glob.glob(f"{IN}/*.wav")):
    name = os.path.splitext(os.path.basename(wav))[0]
    res = f"/kaggle/working/res/{name}"
    try:
        sh(f"python inference.py --driven_audio '{wav}' --source_image '{portrait}' --result_dir '{res}' "
           f"--still --preprocess full --enhancer gfpgan --size 512 --expression_scale 1.0")
        vids = sorted(glob.glob(f"{res}/**/*.mp4", recursive=True), key=os.path.getmtime)
        final = [v for v in vids if "enhanced" in v] or vids
        shutil.copy(final[-1], f"{OUT}/{name}.mp4")
        print(f"OK {name}")
    except Exception as exc:
        failed.append(name)
        print(f"FAILED {name}: {exc}")

shutil.rmtree("/kaggle/working/res", ignore_errors=True)
shutil.rmtree(ST, ignore_errors=True)  # keep the output small
print("done; failed:", failed)
sys.exit(1 if failed and len(failed) == len(glob.glob(f"{IN}/*.wav")) else 0)
