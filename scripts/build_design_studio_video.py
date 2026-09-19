"""Scripted Design Studio demo video: VPC/IAM honesty + generate path + paper.

Writes docs/media/design-studio-demo.mp4 (+ poster) for GitHub Pages.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "media" / "design-studio"
FRAMES = OUT_DIR / "frames"
FFMPEG = Path(
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
)
W, H = 1280, 720
BG = (7, 14, 12)
ACCENT = (61, 207, 142)
GOLD = (224, 192, 122)
TEXT = (232, 240, 234)
MUTED = (127, 153, 140)
PANEL = (14, 26, 22)


def font(size: int, bold: bool = False):
    for path in (
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 210, H), fill=(12, 22, 19))
    draw.rectangle((210, 0, W, 88), fill=(10, 18, 15))
    draw.text((28, 28), "PVDM", fill=ACCENT, font=font(22, True))
    draw.text((28, 58), "Data Mesh", fill=TEXT, font=font(14))
    for i, label in enumerate(["Design", "Overview", "Pipelines", "Trust", "PVDM"]):
        y = 110 + i * 48
        if i == 0:
            draw.rectangle((16, y - 8, 194, y + 28), fill=(20, 48, 36))
            draw.rectangle((16, y - 8, 20, y + 28), fill=ACCENT)
        draw.text((36, y), label, fill=ACCENT if i == 0 else MUTED, font=font(16))
    return img, draw


def caption(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.rectangle((0, H - 110, W, H), fill=(6, 14, 11))
    draw.rectangle((0, H - 110, 8, H), fill=ACCENT)
    y = H - 88
    for line in text.split("\n")[:3]:
        draw.text((28, y), line, fill=TEXT, font=font(24))
        y += 30


def slide(path: Path, title: str, body: list[str], cap: str) -> None:
    img, draw = base()
    draw.text((240, 28), "Mesh Design Studio", fill=TEXT, font=font(28, True))
    draw.text((240, 62), "Create · Observe · Deploy", fill=GOLD, font=font(14))
    draw.rounded_rectangle((240, 110, W - 40, H - 130), radius=18, fill=PANEL, outline=(40, 70, 55))
    draw.text((270, 140), title, fill=GOLD, font=font(22, True))
    y = 190
    for line in body:
        draw.text((270, y), line, fill=TEXT, font=font(20))
        y += 36
    caption(draw, cap)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    if FRAMES.exists():
        for f in FRAMES.glob("*.png"):
            f.unlink()
    FRAMES.mkdir(parents=True, exist_ok=True)

    slides = [
        (
            "01.png",
            "1 · Design-first studio",
            [
                "Left rail: Design is home",
                "Palette → medallion canvas → live contract",
                "Generate writes mesh.yaml + apply → generated/",
            ],
            "Design Studio: compose domains, then generate pipelines in-project.",
        ),
        (
            "02.png",
            "2 · VPC default (honest)",
            [
                "Default = NO VPC attachment",
                "Not your account default VPC",
                "AWS-managed Lambda network for public AWS APIs",
                "Optional: set subnet + SG IDs in tfvars / Design UI",
            ],
            "Networking default: no VPC. Attach only when you need private ENIs.",
        ),
        (
            "03.png",
            "3 · IAM roles (Terraform)",
            [
                "Terraform creates *-domain-writer role",
                "+ Step Functions + EventBridge roles",
                "You do not paste role ARNs in the Design UI",
                "VPC ENI policy attached for optional VPC",
            ],
            "IAM is Terraform-owned. Design UI only sets account IDs + networking mode.",
        ),
        (
            "04.png",
            "4 · Paper + Pages",
            [
                "Research paper: arXiv:2608.14643 (PDF)",
                "GitHub Pages docs site embeds demos",
                "Local UI remains the deploy control plane",
            ],
            "Paper: https://arxiv.org/pdf/2608.14643 · Pages: docs/ on GitHub Actions.",
        ),
        (
            "05.png",
            "5 · Path to AWS",
            [
                "1 Design → 2 Generate → 3 Package",
                "4 terraform apply (prod env)",
                "5 Step Functions run · PVDM gate",
            ],
            "End-to-end: Design → Generate → package → Terraform → SFN / PVDM.",
        ),
    ]

    for name, title, body, cap in slides:
        slide(FRAMES / name, title, body, cap)

    list_file = OUT_DIR / "concat.txt"
    # 3.5s per slide
    lines = []
    for name, *_ in slides:
        lines.append(f"file '{(FRAMES / name).as_posix()}'")
        lines.append("duration 3.5")
    lines.append(f"file '{(FRAMES / slides[-1][0]).as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out_mp4 = ROOT / "docs" / "media" / "design-studio-demo.mp4"
    poster = ROOT / "docs" / "media" / "design-studio-demo-poster.png"
    Image.open(FRAMES / "01.png").save(poster)

    ffmpeg = FFMPEG if FFMPEG.is_file() else Path("ffmpeg")
    cmd = [
        str(ffmpeg),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    print(f"Wrote {out_mp4}")
    print(f"Poster {poster}")


if __name__ == "__main__":
    main()
