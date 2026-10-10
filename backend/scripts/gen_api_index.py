"""Regenerate the endpoint index in docs/API.md from the live OpenAPI schema.

    python -m scripts.gen_api_index

Everything between the BEGIN/END markers is replaced; the hand-written conventions stay.
"""

from collections import defaultdict
from pathlib import Path

from app.main import app

DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"
BEGIN, END = "<!-- BEGIN ENDPOINTS (generated) -->", "<!-- END ENDPOINTS -->"


def render() -> str:
    by_tag: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for path, ops in app.openapi()["paths"].items():
        for method, op in ops.items():
            auth = "🔒" if "security" in op else ""
            summary = (op.get("description") or op.get("summary") or "").strip().split("\n")[0]
            by_tag[(op.get("tags") or ["other"])[0]].append((method.upper(), path, auth, summary))
    out = [BEGIN, ""]
    for tag in sorted(by_tag, key=lambda t: (t.startswith("admin"), t)):
        out += [f"### {tag}", "", "| Method | Path | Notes |", "|---|---|---|"]
        out += [
            f"| `{m}` | `{p}` | {a} {s} |".replace("  |", " |")
            for m, p, a, s in sorted(by_tag[tag], key=lambda r: (r[1], r[0]))
        ]
        out.append("")
    out.append(END)
    return "\n".join(out)


def main() -> None:
    text = DOC.read_text()
    start, end = text.index(BEGIN), text.index(END) + len(END)
    DOC.write_text(text[:start] + render() + text[end:])
    print(f"Updated {DOC}")


if __name__ == "__main__":
    main()
