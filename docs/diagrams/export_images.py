#!/usr/bin/env python3
"""Export .excalidraw diagrams to SVG and PNG using excalidraw-brute-export-cli.

Usage:
    python docs/diagrams/export_images.py                       # export all (SVG + PNG)
    python docs/diagrams/export_images.py etl-pipeline-lineage  # export one
    python docs/diagrams/export_images.py --format svg          # SVG only

Requires: npm install -g excalidraw-brute-export-cli
          npx playwright install firefox
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def export_diagram(excalidraw_path: Path, formats: list[str], scale: int = 2) -> list[Path]:
    """Export one .excalidraw file. Returns output paths."""
    stem = excalidraw_path.stem
    outputs = []

    for fmt in formats:
        out_path = excalidraw_path.parent / f"{stem}.{fmt}"
        print(f"  {stem}.{fmt} ...", end=" ", flush=True)

        try:
            result = subprocess.run(
                [
                    "npx", "excalidraw-brute-export-cli",
                    "-i", str(excalidraw_path),
                    "-o", str(out_path),
                    "-f", fmt,
                    "-s", str(scale),
                ],
                capture_output=True, text=True, timeout=120,
            )
            if out_path.exists() and out_path.stat().st_size > 0:
                size_kb = out_path.stat().st_size / 1024
                print(f"✓ ({size_kb:.0f} KB)")
                outputs.append(out_path)
            else:
                print(f"✗ {result.stderr.strip()[-200:]}")
        except FileNotFoundError:
            print("✗ npx not found. Install Node.js first.")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            print("✗ Timed out")

    return outputs


def main():
    parser = argparse.ArgumentParser(description="Export Excalidraw diagrams to images")
    parser.add_argument("name", nargs="?", help="Diagram name (without extension). Omit for all.")
    parser.add_argument("--format", choices=["svg", "png", "both"], default="both")
    parser.add_argument("--scale", type=int, default=2, help="Export scale (default: 2)")
    args = parser.parse_args()

    formats = ["svg", "png"] if args.format == "both" else [args.format]

    if args.name:
        path = SCRIPT_DIR / f"{args.name}.excalidraw"
        if not path.exists():
            print(f"Error: {path} not found")
            sys.exit(1)
        files = [path]
    else:
        files = sorted(SCRIPT_DIR.glob("*.excalidraw"))

    if not files:
        print("No .excalidraw files found.")
        sys.exit(1)

    print(f"Exporting {len(files)} diagram(s)...\n")

    all_outputs = []
    for f in files:
        print(f"📊 {f.name}")
        outputs = export_diagram(f, formats, scale=args.scale)
        all_outputs.extend(outputs)

    if all_outputs:
        print(f"\n✓ {len(all_outputs)} file(s) exported:")
        for p in all_outputs:
            print(f"  {p}")
    else:
        print("\n✗ No files exported. Ensure excalidraw-brute-export-cli is installed:")
        print("  npm install excalidraw-brute-export-cli")
        print("  npx playwright install firefox")


if __name__ == "__main__":
    main()
