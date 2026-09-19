"""Rebuild Design Studio demo video — create mesh (region/accounts/VPC)."""

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


def slide(path: Path, title: str, lines: list[str], cap: str, highlight: int | None = None) -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 72), fill=(10, 18, 15))
    draw.text((36, 22), "Create data mesh", fill=GOLD, font=font(16, True))
    draw.text((220, 18), "Mesh Design Studio", fill=TEXT, font=font(28, True))
    draw.rounded_rectangle((40, 100, W - 40, H - 120), radius=20, fill=PANEL, outline=(40, 70, 55))
    draw.text((70, 130), title, fill=GOLD, font=font(26, True))
    y = 190
    for i, line in enumerate(lines):
        box = (70, y - 8, W - 70, y + 48)
        if highlight is not None and i == highlight:
            draw.rounded_rectangle(box, radius=10, fill=(20, 48, 36), outline=ACCENT)
        draw.text((90, y), line, fill=TEXT if highlight != i else ACCENT, font=font(22))
        y += 64
    draw.rectangle((0, H - 100, W, H), fill=(6, 14, 11))
    draw.rectangle((0, H - 100, 8, H), fill=ACCENT)
    cy = H - 78
    for part in cap.split("\n")[:2]:
        draw.text((28, cy), part, fill=TEXT, font=font(24))
        cy += 32
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    slides = [
        (
            "v2-01.png",
            "1 · Where — region",
            [
                "Organization + name prefix",
                "AWS region dropdown (us-east-2, …)",
                "Written into mesh.yaml + terraform.contract.txt",
            ],
            "Step 1: choose the AWS region for this data mesh.",
            1,
        ),
        (
            "v2-02.png",
            "2 · Accounts",
            [
                "Single account (POC) — one ID for all roles",
                "OR three accounts — Producer · Steward · Publisher",
                "IAM roles are Terraform-created (no role ARNs in UI)",
            ],
            "Step 2: pick account topology and 12-digit account IDs.",
            0,
        ),
        (
            "v2-03.png",
            "3 · VPC — three choices",
            [
                "Default — no VPC (AWS-managed; NOT account default VPC)",
                "Use existing VPC — paste subnet + security group IDs",
                "Create new VPC — Terraform module vpc-lambda",
            ],
            "Step 3: networking is an explicit choice during mesh creation.",
            None,
        ),
        (
            "v2-04.png",
            "Create new VPC details",
            [
                "vpc_mode = create",
                "CIDR e.g. 10.80.0.0/16",
                "2 or 3 AZs → private subnets + Lambda SG",
            ],
            "Create mode: Terraform builds private networking for Lambda ENIs.",
            0,
        ),
        (
            "v2-05.png",
            "Then generate",
            [
                "Drop bronze → silver → gold domains",
                "Generate → mesh.yaml + apply → generated/",
                "terraform apply uses vpc_mode from the contract hint",
            ],
            "Design → Generate → package → Terraform. Video player uses direct MP4 src.",
            1,
        ),
    ]
    for name, title, lines, cap, hi in slides:
        slide(FRAMES / name, title, lines, cap, hi)

    concat = OUT_DIR / "concat.txt"
    lines_out: list[str] = []
    for name, *_ in slides:
        lines_out.append(f"file '{(FRAMES / name).resolve().as_posix()}'")
        lines_out.append("duration 4")
    lines_out.append(f"file '{(FRAMES / slides[-1][0]).resolve().as_posix()}'")
    concat.write_text("\n".join(lines_out) + "\n", encoding="utf-8")

    out = ROOT / "docs" / "media" / "design-studio-demo.mp4"
    poster = ROOT / "docs" / "media" / "design-studio-demo-poster.png"
    Image.open(FRAMES / "v2-03.png").save(poster)

    ffmpeg = str(FFMPEG if FFMPEG.is_file() else "ffmpeg")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-profile:v",
            "main",
            "-level",
            "4.0",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
