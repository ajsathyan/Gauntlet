#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_RE = re.compile(
    r'(<script\b(?=[^>]*\bid=["\']review-brief-data["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>)(.*?)(</script>)',
    re.S,
)


def html_safe_json(data):
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def main():
    parser = argparse.ArgumentParser(
        description="Embed review-brief-data.json into review-brief.html for file:// review."
    )
    parser.add_argument("root", nargs="?", default=".", help="Project root containing review brief files.")
    parser.add_argument("--html", default="review-brief.html", help="HTML file relative to root.")
    parser.add_argument("--data", default="review-brief-data.json", help="JSON data file relative to root.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    html_path = root / args.html
    data_path = root / args.data

    if not html_path.is_file():
        print(f"missing review brief HTML: {html_path}", file=sys.stderr)
        return 1
    if not data_path.is_file():
        print(f"missing review brief data: {data_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(data_path.read_text())
    except json.JSONDecodeError as error:
        print(f"invalid review brief JSON: {error}", file=sys.stderr)
        return 1

    html = html_path.read_text()
    embedded = html_safe_json(data)

    def replace(match):
        return f"{match.group(1)}\n{embedded}\n{match.group(3)}"

    next_html, count = SCRIPT_RE.subn(replace, html, count=1)
    if count != 1:
        print("review brief HTML is missing the review-brief-data application/json script", file=sys.stderr)
        return 1

    html_path.write_text(next_html)
    print(f"Embedded {data_path.name} into {html_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
