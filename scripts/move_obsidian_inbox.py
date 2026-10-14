"""Move one Inbox document into a confirmed University resource folder."""

from __future__ import annotations

import argparse

from integrations.obsidian_processor import move_inbox_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("relative_path", help="ex: 07 Notes/Inbox/curs.pdf")
    parser.add_argument("--subject", required=True, help="numele exact al materiei")
    parser.add_argument("--type", required=True, choices=("Cursuri", "Seminarii"))
    parser.add_argument("--confirm", action="store_true", help="confirmă mutarea")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("mutarea necesită --confirm")
    print(move_inbox_document(args.relative_path, args.subject, args.type))


if __name__ == "__main__":
    main()
