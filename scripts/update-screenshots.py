"""Rebuild the README screenshot gallery from screenshots/*.png (run by .github/workflows/update-screenshots.yml).

Same idea as the Ltek card repos: everything between the SCREENSHOTS markers is regenerated. Images are sorted by
file name; a leading "NN-" is dropped from the caption ("04-server-device.png" -> "Server device").
Two per row: these are full-width page shots.
"""

import re
from pathlib import Path

README = Path("README.md")
SCREENSHOTS = Path("screenshots")
START = "<!-- SCREENSHOTS:START -->"
END = "<!-- SCREENSHOTS:END -->"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PER_ROW = 2


def caption(path: Path) -> str:
    """'03-zone-editor' -> 'Zone editor'."""
    text = re.sub(r"^\d+[-_ ]*", "", path.stem).replace("_", " ").replace("-", " ").strip()
    return text[:1].upper() + text[1:]


def image_grid() -> str:
    """The gallery table between the markers."""
    images = sorted(p for p in SCREENSHOTS.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    rows = []
    for i in range(0, len(images), PER_ROW):
        cells = [
            f'    <td align="center" valign="top" width="{100 // PER_ROW}%">\n'
            f'      <a href="screenshots/{img.name}">'
            f'<img src="screenshots/{img.name}" width="100%" alt="{caption(img)}"></a>'
            f"<br><sub>{caption(img)}</sub>\n    </td>"
            for img in images[i : i + PER_ROW]
        ]
        cells += ["    <td></td>"] * (PER_ROW - len(cells))
        rows.append("  <tr>\n" + "\n".join(cells) + "\n  </tr>")
    return f"{START}\n<table>\n" + "\n".join(rows) + f"\n</table>\n{END}"


def main() -> None:
    """Replace (or append) the gallery."""
    if not README.exists() or not SCREENSHOTS.exists():
        raise SystemExit("README.md or screenshots/ not found")
    content = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if pattern.search(content):
        content = pattern.sub(lambda _m: image_grid(), content)
    else:
        content = content.rstrip("\n") + "\n\n" + image_grid() + "\n"
    README.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
