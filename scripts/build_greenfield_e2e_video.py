"""Generate captioned greenfield E2E control-UI demo video for GitHub Pages.

Honest product story: YAML/JSON metadata → compiler → all layers → UI observe → Terraform.
Not a diagram-draw designer.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "media" / "greenfield-e2e"
FRAMES = OUT_DIR / "frames"
UI = ROOT / "docs" / "images" / "ui-demo"
FFMPEG = Path(
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
)
W, H = 1280, 720
BG = (8, 17, 14)
PANEL = (18, 32, 27)
ACCENT = (61, 207, 142)
GOLD = (232, 196, 122)
TEXT = (232, 240, 234)
MUTED = (143, 168, 153)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def card_base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    # soft orbs
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -80, 520, 420), fill=(22, 53, 40, 90))
    od.ellipse((780, -40, 1400, 480), fill=(26, 42, 24, 70))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    return img, draw


def wrap_lines(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(para, width=max_chars) or [""])
    return lines


def draw_caption_bar(draw: ImageDraw.ImageDraw, caption: str) -> None:
    bar_h = 118
    draw.rectangle((0, H - bar_h, W, H), fill=(6, 16, 12))
    draw.rectangle((0, H - bar_h, 8, H), fill=ACCENT)
    y = H - bar_h + 18
    for line in wrap_lines(caption, 78)[:3]:
        draw.text((28, y), line, fill=TEXT, font=font(26))
        y += 32


def title_frame(
    path: Path,
    eyebrow: str,
    title: str,
    subtitle: str,
    caption: str,
) -> None:
    img, draw = card_base()
    draw.rounded_rectangle((48, 80, W - 48, H - 150), radius=24, fill=PANEL, outline=(60, 90, 72))
    draw.text((80, 110), eyebrow.upper(), fill=GOLD, font=font(20, bold=True))
    ty = 160
    for line in wrap_lines(title, 28):
        draw.text((80, ty), line, fill=TEXT, font=font(48, bold=True))
        ty += 58
    sy = ty + 16
    for line in wrap_lines(subtitle, 56):
        draw.text((80, sy), line, fill=MUTED, font=font(24))
        sy += 34
    draw_caption_bar(draw, caption)
    img.save(path)


def bullet_frame(path: Path, title: str, bullets: list[str], caption: str) -> None:
    img, draw = card_base()
    draw.rounded_rectangle((48, 60, W - 48, H - 150), radius=24, fill=PANEL, outline=(60, 90, 72))
    draw.text((80, 90), title, fill=TEXT, font=font(36, bold=True))
    y = 160
    for b in bullets:
        draw.ellipse((88, y + 10, 104, y + 26), fill=ACCENT)
        for i, line in enumerate(wrap_lines(b, 62)):
            draw.text((120, y + i * 30), line, fill=TEXT, font=font(24))
        y += 30 * max(1, len(wrap_lines(b, 62))) + 18
    draw_caption_bar(draw, caption)
    img.save(path)


def code_frame(path: Path, title: str, code: str, caption: str) -> None:
    img, draw = card_base()
    draw.rounded_rectangle((48, 60, W - 48, H - 150), radius=24, fill=PANEL, outline=(60, 90, 72))
    draw.text((80, 85), title, fill=GOLD, font=font(22, bold=True))
    y = 130
    mono = font(20)
    for line in code.splitlines():
        draw.text((80, y), line, fill=ACCENT if line.startswith(("$", "#")) else TEXT, font=mono)
        y += 28
    draw_caption_bar(draw, caption)
    img.save(path)


def screenshot_frame(path: Path, src: Path, caption: str) -> None:
    img, draw = card_base()
    shot = Image.open(src).convert("RGB")
    # fit above caption bar
    max_h = H - 150 - 40
    max_w = W - 80
    ratio = min(max_w / shot.width, max_h / shot.height)
    nw, nh = int(shot.width * ratio), int(shot.height * ratio)
    shot = shot.resize((nw, nh), Image.Resampling.LANCZOS)
    x, y = (W - nw) // 2, 30 + (max_h - nh) // 2
    # shadow panel
    draw.rounded_rectangle((x - 8, y - 8, x + nw + 8, y + nh + 8), radius=16, fill=(4, 10, 8))
    img.paste(shot, (x, y))
    draw = ImageDraw.Draw(img)
    draw_caption_bar(draw, caption)
    img.save(path)


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    for p in FRAMES.glob("*.png"):
        p.unlink()

    # Scene plan: greenfield developer → metadata → compile XYZ layers → UI → E2E
    scenes: list[tuple[str, float]] = []

    def add(name: str, seconds: float) -> Path:
        path = FRAMES / f"{len(scenes):02d}-{name}.png"
        scenes.append((path.name, seconds))
        return path

    title_frame(
        add("open", 4.0),
        "Greenfield developer story",
        "From empty repo to XYZ mesh",
        "Metadata-ready contract → compiler creates all layers → control UI observes → Terraform deploys.",
        "No diagram canvas today. Pipelines come from YAML/JSON metadata + apply — UI is for explore/trust.",
    )
    bullet_frame(
        add("intent", 4.5),
        "What the developer wants",
        [
            "Brand-new domain product: xyz (bronze → silver → gold)",
            "Proof-gated writes (VRP PASS before Iceberg metadata)",
            "Local UI to inspect pipelines before spending AWS $",
            "Then package Lambda + Terraform + Step Functions run",
        ],
        "Goal: one medallion contract expands into every layer pipeline automatically.",
    )
    code_frame(
        add("scaffold", 5.0),
        "Step 1 — Scaffold metadata (not draw)",
        "$ serverless-data-mesh new --template medallion --output xyz-mesh\n"
        "$ code xyz-mesh/mesh.yaml\n"
        "\n"
        "apiVersion: sdm/v1\n"
        "kind: MedallionMesh\n"
        "spec:\n"
        "  domains:\n"
        "    - domain_id: xyz\n"
        "      layers: { bronze, silver, gold }",
        "Edit the contract in YAML (JSON-compatible metadata). Closest “magic”: one file → many pipelines.",
    )
    code_frame(
        add("apply", 5.0),
        "Step 2 — Compile all layers",
        "$ serverless-data-mesh apply \\\n"
        "    --contract xyz-mesh/mesh.yaml \\\n"
        "    --output xyz-mesh/generated\n"
        "\n"
        "# Emits for each layer:\n"
        "#   handler.py · readers.py · Step Functions ASL\n"
        "#   VRP config · consumer SLAs · manifests",
        "Compiler materializes bronze, silver, and gold writers + mesh orchestrator stubs.",
    )
    bullet_frame(
        add("layers", 4.5),
        "XYZ pipelines created (all layers)",
        [
            "xyz-bronze — land raw events (Physical + VRP gate)",
            "xyz-silver — curated transforms (optional SparkRules / PySpark)",
            "xyz-gold — consumer-ready product + SLA hooks",
            "Mesh orchestrator — schedule / fan-out across layers",
        ],
        "Same PVDM invariant on every layer: commit_metadata ⟹ VRP = PASS.",
    )
    code_frame(
        add("ui-start", 4.0),
        "Step 3 — Start local control UI",
        "$ serverless-data-mesh ui \\\n"
        "    --path xyz-mesh/generated --open\n"
        "\n"
        "# Python ThreadingHTTPServer (not Jetty)\n"
        "# → http://127.0.0.1:8765/\n"
        "# Tabs: Overview · Pipelines · Trust · PVDM · Durable · Tutorial",
        "UI reads generated manifests. It does not design or draw the mesh.",
    )

    # Real UI screenshots (northstar sample = same product shape as XYZ medallion)
    screenshot_frame(
        add("ui-overview", 3.5),
        UI / "01-overview.png",
        "Overview: KPIs for pipelines, domains, readers readiness, VRP pass/fail, deploy-ready.",
    )
    screenshot_frame(
        add("ui-pipelines", 4.0),
        UI / "02-pipelines.png",
        "Pipelines tab: every bronze/silver/gold row the compiler emitted (handler + readers status).",
    )
    screenshot_frame(
        add("ui-trust", 3.5),
        UI / "03-trust.png",
        "Trust board: VRP PASS/FAIL by domain. Corrupt data never becomes Iceberg metadata.",
    )
    screenshot_frame(
        add("ui-pvdm", 3.5),
        UI / "04-pvdm.png",
        "PVDM phases: Physical → Verify → Durable → Metadata. Fail-closed on VRP FAIL.",
    )
    screenshot_frame(
        add("ui-durable", 3.5),
        UI / "05-durable.png",
        "Dual clocks: segment timeout vs durable workload budget (resume after rolled_back).",
    )
    screenshot_frame(
        add("ui-demo", 3.5),
        UI / "07-overview-after-demo.png",
        "Run PVDM demo locally: clean commit passes; corrupt write is blocked (no AWS required).",
    )

    code_frame(
        add("readers", 4.0),
        "Step 4 — Wire I/O, then package",
        "$ serverless-data-mesh doctor --path xyz-mesh/generated\n"
        "# implement each layer readers.py (source / sink)\n"
        "\n"
        "$ ./infrastructure/terraform/scripts/package_lambda.sh\n"
        "$ cd infrastructure/terraform/environments/prod\n"
        "$ terraform apply",
        "Fill stubs the compiler left, build the Lambda zip, apply Terraform for the domain stack.",
    )
    bullet_frame(
        add("runtime", 4.5),
        "Step 5 — How it runs end to end on AWS",
        [
            "EventBridge / operator starts Step Functions",
            "Lambda segment writes Parquet via IceGuard (Physical)",
            "VRP verifies source↔sink; FAIL stops metadata",
            "Durable resume on rolled_back until committed",
            "Glue/Iceberg snapshot only after VRP PASS",
        ],
        "Consumers only see proof-gated gold products — not green job logs alone.",
    )
    title_frame(
        add("close", 4.0),
        "Ship checklist",
        "Metadata → apply → UI → Terraform",
        "Diagram-to-mesh designer is a future feature. Web contract editor is roadmap. Today’s high-value path is the compiler.",
        "Docs: developer-ui-and-deploy.md · GitHub Pages embeds this captioned demo.",
    )

    # concat list
    list_path = OUT_DIR / "frames.txt"
    lines: list[str] = []
    for name, dur in scenes:
        lines.append(f"file '{FRAMES.as_posix()}/{name}'")
        lines.append(f"duration {dur}")
    # concat demuxer needs last file repeated
    lines.append(f"file '{FRAMES.as_posix()}/{scenes[-1][0]}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="ascii")

    out_mp4 = ROOT / "docs" / "media" / "greenfield-e2e-captioned.mp4"
    poster = ROOT / "docs" / "media" / "greenfield-e2e-poster.png"
    Image.open(FRAMES / scenes[0][0]).save(poster)

    cmd = [
        str(FFMPEG),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Wrote", out_mp4, "size", out_mp4.stat().st_size)


if __name__ == "__main__":
    main()
