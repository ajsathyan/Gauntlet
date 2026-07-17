"""Saved-diagram CLI command."""

import json


def command_find(args, *, root):
    index = root / "docs" / "gauntlet-diagrams" / "index.md"
    matches = []
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| `") or args.query.lower() not in line.lower():
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= 5:
                matches.append(
                    {
                        "id": cells[0].strip("`"),
                        "title": cells[1],
                        "feature": cells[2].strip("`"),
                        "tags": [
                            tag.strip().strip("`")
                            for tag in cells[3].split(",")
                        ],
                        "path": cells[4].strip("`"),
                    }
                )
    payload = {"schemaVersion": "1.0", "status": "pass", "matches": matches}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for match in matches:
            print(f"{match['id']}: {match['path']}")
    return 0


def register(subcommands, *, command):
    diagram = subcommands.add_parser("diagram", help="Saved diagram helpers.")
    commands = diagram.add_subparsers(dest="diagram_command", required=True)
    find = commands.add_parser("find")
    find.add_argument("--query", required=True)
    find.add_argument("--json", action="store_true")
    find.set_defaults(func=command)
