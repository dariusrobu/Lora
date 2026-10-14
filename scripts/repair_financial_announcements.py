"""Repair the verified legacy duplicate export, retaining a timestamped backup."""
from datetime import datetime
from pathlib import Path
import re
import shutil

from scripts.moodle_bridge import _ordered_announcements


def main() -> None:
    vault = Path('/Users/robu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Lora')
    note = vault / '05 University/Analiză financiară/Anunțuri/Analiză-financiară_EG3_26-27.md'
    text = note.read_text(encoding='utf-8')
    start, end = '<!-- LORA:MOODLE:START -->', '<!-- LORA:MOODLE:END -->'
    before, managed = text.split(start, 1)
    managed, tail = managed.split(end, 1)
    # Remove the legacy tail only if every complete dated post is already present.
    legacy = re.split(r'(?=^### )', tail, flags=re.MULTILINE)
    posts = [part.strip() for part in legacy if '**Data:**' in part]
    for post in posts:
        normalized = post.replace('### ', '## ', 1)
        if normalized not in managed:
            raise RuntimeError('Legacy content differs; manual reconciliation required')
    if tail.strip() and not posts:
        raise RuntimeError('Unexpected manual content; refusing to discard it')
    backup = vault / '99 Archive' / ('announcement-repair-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    shutil.copy2(note, backup / note.name)
    note.write_text(before + start + '\n' + _ordered_announcements(managed.strip()) + end + '\n', encoding='utf-8')
    result = note.read_text(encoding='utf-8')
    assert result.count('## SEMINAR 13 octombrie 2026') == 1
    assert result.count('## RECUPERARE Seminar') == 1
    assert result.index('## SEMINAR 13') < result.index('## RECUPERARE')
    print('Verified: 2 unique announcements, 12 October then 6 October. Backup:', backup)


if __name__ == '__main__':
    main()
