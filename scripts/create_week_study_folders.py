"""Add Curs/Seminar directories to existing canonical subject weeks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.moodle_bridge import _ensure_week_subfolders

ROOT = Path('/Users/robu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Lora/05 University')
SUBJECTS = (
    'Analiză financiară', 'Bazele econometriei', 'Jurnalism economic',
    'Macroeconomie aprofundată', 'Marketing în comerț',
    'Politici comerciale', 'Politici de marketing',
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    counts: dict[str, int] = {}
    weeks: list[Path] = []
    for name in SUBJECTS:
        subject = ROOT / name
        selected = [path for path in subject.iterdir()
                    if re.fullmatch(r'Săptămâna [1-9][0-9]*', path.name)
                    and path.is_dir() and not path.is_symlink()]
        counts[name] = len(selected)
        weeks.extend(selected)
    missing = [week / name for week in weeks for name in ('Curs', 'Seminar')
               if not (week / name).exists()]
    if args.apply:
        for week in weeks:
            _ensure_week_subfolders(week, ROOT)
        if not all((week / name).is_dir() for week in weeks for name in ('Curs', 'Seminar')):
            raise RuntimeError('Verificarea folderelor a eșuat')
    print(json.dumps({'weeks_by_subject': counts, 'total_weeks': len(weeks),
                      'folders_created' if args.apply else 'folders_to_create': len(missing),
                      'verified': args.apply}, ensure_ascii=False))


if __name__ == '__main__':
    main()
