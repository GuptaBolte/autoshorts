"""Generates several candidate Krishna portraits for lip-sync. Pick the best one and save it as
assets/characters/krishna.jpg; every talking shot then uses that exact face.

Lip-sync works best with: front-facing, face centered in the upper half, mouth closed, eyes open, nothing covering the face.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import images  # noqa: E402

cfg = json.load(open("channels/spiritual/config.json"))
desc = cfg["characters"]["KRISHNA"].replace(", holding a bansuri flute", "")
prompt = (f"head and shoulders portrait of {desc}, facing the camera directly, looking straight into the lens, "
          f"eyes open, lips gently closed, serene expression, face fully visible and unobstructed, face in the upper "
          f"third of the frame, soft temple background with golden light, {cfg['visual_style']}")
os.makedirs("out/portraits", exist_ok=True)
for seed in [11, 23, 37, 51, 68, 84, 97, 120]:
    images.generate(prompt, f"out/portraits/krishna_seed{seed}.jpg", seed=seed)
print("done")
