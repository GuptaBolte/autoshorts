"""Builds an .ass subtitle file: punchy 2-4 word caption chunks plus an optional top title."""

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,80,80,{margin},1
Style: Title,{font},64,&H0066DDFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,8,70,70,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(sec: float) -> str:
    sec = max(sec, 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def chunk_words(text: str, size: int = 3):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def build(beats_timing, out_path: str, font: str = "DejaVu Sans", size: int = 86, margin: int = 520,
          words_per_chunk: int = 3):
    """beats_timing: list of dicts {start, end, caption, on_screen_text}."""
    lines = [HEADER.format(font=font, size=size, margin=margin)]
    for beat in beats_timing:
        start, end = beat["start"], beat["end"]
        if beat.get("on_screen_text"):
            lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Title,,0,0,0,,{_esc(beat['on_screen_text'].upper())}")
        chunks = chunk_words(beat.get("caption", ""), words_per_chunk)
        if not chunks:
            continue
        # weight each chunk by its character length, so longer phrases stay on screen longer
        weights = [max(len(c), 4) for c in chunks]
        total, t = sum(weights), start
        for chunk, w in zip(chunks, weights):
            d = (end - start) * w / total
            lines.append(f"Dialogue: 0,{_ts(t)},{_ts(t + d)},Cap,,0,0,0,,{_esc(chunk)}")
            t += d
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
