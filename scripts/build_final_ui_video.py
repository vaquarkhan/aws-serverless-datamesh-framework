"""Capture final Control UI demo frames from the live Design Studio and encode MP4.

Requires the local UI on http://127.0.0.1:8765/ (or SDM_UI_BASE).
Uses Playwright if available; otherwise builds captioned slides (offline fallback).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "media"
FRAMES = OUT_DIR / "final-ui" / "frames"
FFMPEG = Path(
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
)
BASE = os.environ.get("SDM_UI_BASE", "http://127.0.0.1:8765/")
W, H = 1280, 720


def font(size: int, bold: bool = False):
    for path in (
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def caption_overlay(img: Image.Image, text: str) -> Image.Image:
    img = img.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, H - 100, W, H), fill=(6, 14, 11))
    draw.rectangle((0, H - 100, 8, H), fill=(61, 207, 142))
    y = H - 78
    for line in text.split("\n")[:2]:
        draw.text((24, y), line, fill=(232, 240, 234), font=font(24))
        y += 32
    return img


def slide(path: Path, title: str, bullets: list[str], cap: str) -> None:
    img = Image.new("RGB", (W, H), (7, 14, 12))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 70), fill=(10, 18, 15))
    draw.text((32, 20), "Serverless Data Mesh — final UI tour", fill=(224, 192, 122), font=font(18, True))
    draw.rounded_rectangle((40, 100, W - 40, H - 120), radius=18, fill=(14, 26, 22), outline=(40, 70, 55))
    draw.text((70, 130), title, fill=(224, 192, 122), font=font(28, True))
    y = 200
    for b in bullets:
        draw.text((90, y), "•  " + b, fill=(232, 240, 234), font=font(22))
        y += 48
    draw.rectangle((0, H - 100, W, H), fill=(6, 14, 11))
    draw.rectangle((0, H - 100, 8, H), fill=(61, 207, 142))
    draw.text((24, H - 70), cap, fill=(232, 240, 234), font=font(24))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def capture_playwright(frames: Path) -> list[tuple[str, str]]:
    from playwright.sync_api import sync_playwright

    shots: list[tuple[str, str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(BASE, wait_until="networkidle")

        def snap(name: str, caption: str) -> None:
            raw = frames / f"_{name}.png"
            page.screenshot(path=str(raw), full_page=False)
            caption_overlay(Image.open(raw), caption).save(frames / f"{name}.png")
            shots.append((f"{name}.png", caption))

        snap("01-create", "Create data mesh: region · accounts · VPC")
        page.locator('input[name="design-acct-mode"][value="multi"]').check()
        page.wait_for_timeout(400)
        snap("02-accounts", "Three-account mesh: Producer · Steward · Publisher")
        page.locator('input[name="design-vpc-mode"][value="create"]').check()
        page.wait_for_timeout(400)
        snap("03-vpc-create", "VPC: create new — Terraform vpc-lambda module")
        page.locator('input[name="design-vpc-mode"][value="existing"]').check()
        page.wait_for_timeout(300)
        snap("04-vpc-existing", "VPC: use existing — paste subnet + SG IDs")
        page.locator('input[name="design-vpc-mode"][value="none"]').check()
        page.click("#btn-design-sample")
        page.wait_for_timeout(500)
        snap("05-domains", "Domains: bronze → silver → gold on the canvas")
        page.click('button.rail-item[data-tab="pipelines"]')
        page.wait_for_timeout(500)
        snap("06-pipelines", "Pipelines tab: compiled layer handlers under generated/")
        page.click('button.rail-item[data-tab="pvdm"]')
        page.wait_for_timeout(500)
        snap("07-pvdm", "PVDM invariant + research paper arXiv:2608.14643")
        browser.close()
    return shots


def capture_fallback(frames: Path) -> list[tuple[str, str]]:
    seq = [
        ("01-create", "Create data mesh", ["Region dropdown", "Single or three accounts", "VPC: none / existing / create"], "Create data mesh: region · accounts · VPC"),
        ("02-accounts", "Accounts", ["Single account for POC", "Or Producer · Steward · Publisher", "IAM roles via Terraform"], "Account topology is part of mesh creation"),
        ("03-vpc", "Networking", ["Default = no VPC (not account default)", "Existing = your subnets/SGs", "Create = vpc-lambda module"], "Three honest VPC choices"),
        ("04-generate", "Generate", ["Write mesh.yaml in project", "apply → generated/", "terraform.contract.txt for vpc_mode"], "Generate pipelines in-project — not download-only"),
        ("05-paper", "Paper + Pages", ["arXiv:2608.14643 PDF", "GitHub Pages docs + demos", "Local UI remains control plane"], "Docs site + local Design Studio"),
    ]
    out: list[tuple[str, str]] = []
    for name, title, bullets, cap in seq:
        slide(frames / f"{name}.png", title, bullets, cap)
        out.append((f"{name}.png", cap))
    return out


def encode(shots: list[tuple[str, str]]) -> Path:
    frames = FRAMES
    concat = frames.parent / "concat.txt"
    lines: list[str] = []
    for name, _ in shots:
        lines.append(f"file '{(frames / name).resolve().as_posix()}'")
        lines.append("duration 3.5")
    lines.append(f"file '{(frames / shots[-1][0]).resolve().as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = OUT_DIR / "control-ui-final.mp4"
    poster = OUT_DIR / "control-ui-final-poster.png"
    Image.open(frames / shots[0][0]).save(poster)

    ffmpeg = str(FFMPEG if FFMPEG.is_file() else "ffmpeg")
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out),
        ],
        check=True,
    )
    # Keep design-studio-demo as alias of final for Pages card
    design = OUT_DIR / "design-studio-demo.mp4"
    design.write_bytes(out.read_bytes())
    (OUT_DIR / "design-studio-demo-poster.png").write_bytes(poster.read_bytes())
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    return out


def main() -> int:
    if FRAMES.exists():
        for f in FRAMES.glob("*.png"):
            f.unlink()
    FRAMES.mkdir(parents=True, exist_ok=True)

    shots: list[tuple[str, str]]
    try:
        shots = capture_playwright(FRAMES)
        print("Captured live UI via Playwright")
    except Exception as exc:  # noqa: BLE001
        print(f"Playwright unavailable ({exc}); using captioned slides", file=sys.stderr)
        shots = capture_fallback(FRAMES)

    encode(shots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
