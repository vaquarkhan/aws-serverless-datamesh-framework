"""Build animated GIF tutorials from still frames (Pillow)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    Path.home()
    / ".cursor"
    / "projects"
    / "c-Users-Administrator-Downloads-serverless-datamesh-framework-sdf"
    / "assets"
)
OUT = ROOT / "docs" / "images" / "tutorial"

STEPS = [
    "step-01-install-demo",
    "step-02-new-mesh",
    "step-03-apply",
    "step-04-ui",
    "step-05-deploy",
    "step-06-observe",
]


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pulse_frames(img: Image.Image, *, label: str, n: int = 6) -> list[Image.Image]:
    frames: list[Image.Image] = []
    w, h = img.size
    base = img.convert("RGBA").resize((960, int(960 * h / w)), Image.Resampling.LANCZOS)
    bw, bh = base.size
    for i in range(n):
        frame = base.copy()
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        # progress bar
        bar_w = int((i + 1) / n * (bw - 80))
        draw.rounded_rectangle((40, bh - 48, bw - 40, bh - 28), radius=8, fill=(20, 40, 32, 200))
        draw.rounded_rectangle(
            (40, bh - 48, 40 + bar_w, bh - 28), radius=8, fill=(61, 207, 142, 230)
        )
        # caption chip
        draw.rounded_rectangle(
            (40, 28, 40 + 8 * len(label) + 36, 68), radius=12, fill=(10, 24, 18, 210)
        )
        draw.text((56, 38), label, fill=(232, 240, 234, 255), font=_font(18))
        # subtle brightness pulse
        blended = Image.alpha_composite(frame, overlay)
        enhancer = ImageEnhance.Brightness(blended.convert("RGB"))
        bright = 1.0 + 0.04 * (1 if i % 2 == 0 else 0)
        frames.append(enhancer.enhance(bright))
    return frames


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    overview_frames: list[Image.Image] = []

    for name in STEPS:
        src = ASSETS / f"{name}.png"
        if not src.is_file():
            # fallback: already in OUT
            src = OUT / f"{name}.png"
        if not src.is_file():
            print(f"skip missing {name}")
            continue
        img = Image.open(src)
        # still
        still = img.convert("RGB")
        still_path = OUT / f"{name}.png"
        still.save(still_path, optimize=True)
        # gif
        frames = _pulse_frames(img, label=name.replace("-", " "))
        gif_path = OUT / f"{name}.gif"
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=380,
            loop=0,
            optimize=True,
        )
        overview_frames.append(frames[len(frames) // 2])
        print(f"wrote {still_path.name} + {gif_path.name}")

    if overview_frames:
        overview = OUT / "tutorial-overview.gif"
        overview_frames[0].save(
            overview,
            save_all=True,
            append_images=overview_frames[1:],
            duration=1200,
            loop=0,
            optimize=True,
        )
        print(f"wrote {overview.name}")


if __name__ == "__main__":
    build()
