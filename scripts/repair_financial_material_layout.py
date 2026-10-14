"""Reconcile the known financial-analysis migration leftovers; dry-run by default."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote

VAULT = Path('/Users/robu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Lora')
SUBJECT = VAULT / '05 University/Analiză financiară'


def digest(path: Path) -> str:
    if path.is_symlink():
        raise ValueError(f'Symlink: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generated_body(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    start, end = '<!-- LORA:MOODLE:START -->', '<!-- LORA:MOODLE:END -->'
    if start not in text or end not in text:
        return text
    text = text.split(start, 1)[1].split(end, 1)[0]
    text = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', text)
    return text.strip()


def plan() -> tuple[list[dict[str, str]], dict[str, str], list[Path]]:
    actions: list[dict[str, str]] = []
    aliases: dict[str, str] = {}
    folders = sorted(SUBJECT.glob('Săptămâna */Files - *'))
    folders += sorted((SUBJECT / 'Pregătire intermediară').glob('Files - *'))
    known: dict[Path, dict[str, Path]] = {}
    planned: dict[Path, str] = {}
    for folder in folders:
        match = re.fullmatch(r'Files - Tematică C(\d+)-S\1', folder.name)
        bucket = SUBJECT / f'Săptămâna {int(match[1])}' if match else folder.parent
        target_dir = bucket / 'Files'
        if target_dir not in known:
            known[target_dir] = {}
            for target in sorted(target_dir.glob('*')):
                if target.is_file():
                    known[target_dir].setdefault(digest(target), target)
        for source in sorted(folder.rglob('*')):
            if source.is_symlink():
                raise ValueError(f'Symlink: {source}')
            if not source.is_file():
                continue
            sha = digest(source)
            target = known[target_dir].get(sha)
            kind = 'archive_duplicate' if target else 'move_unique'
            if target is None:
                target = target_dir / source.name
                if target.exists() or target in planned:
                    target = target.with_name(f'{target.stem}-{sha[:12]}{target.suffix}')
                if target.exists() or target in planned:
                    raise ValueError(f'Unresolved collision: {target}')
                known[target_dir][sha] = target
                planned[target] = sha
            actions.append({'source': str(source), 'target': str(target), 'sha256': sha, 'kind': kind})
            new_link = target.relative_to(VAULT).as_posix()
            aliases[source.relative_to(VAULT).as_posix()] = new_link
            section = folder.name.removeprefix('Files - ')
            for legacy in ('Files', 'Resources'):
                old = SUBJECT / 'Moodle' / legacy / section / source.name
                aliases[old.relative_to(VAULT).as_posix()] = new_link
    for number in range(10, 15):
        source = SUBJECT / 'Săptămâna 1' / f'Tematică C{number}-S{number}.md'
        if not source.exists():
            continue
        target = SUBJECT / f'Săptămâna {number}' / source.name
        same = target.exists() and generated_body(source) == generated_body(target)
        if target.exists() and not same:
            target = target.with_stem(target.stem + ' - versiune păstrată')
            if target.exists():
                raise ValueError(f'Collision: {target}')
        actions.append({'source': str(source), 'target': str(target),
                        'sha256': digest(source), 'kind': 'archive_legacy_note' if same else 'move_unique'})
        aliases[source.relative_to(VAULT).as_posix()] = target.relative_to(VAULT).as_posix()
    return actions, aliases, folders


def apply(actions: list[dict[str, str]], aliases: dict[str, str], folders: list[Path]) -> None:
    # Full preflight before changing any source.
    for action in actions:
        if digest(Path(action['source'])) != action['sha256']:
            raise ValueError('Source changed since planning')
    archive = VAULT / '99 Archive' / ('financial-layout-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    archive.mkdir(parents=True, exist_ok=False)
    (archive / 'manifest.json').write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding='utf-8')
    for action in actions:
        source, target = Path(action['source']), Path(action['target'])
        if action['kind'] == 'archive_duplicate' and digest(target) != action['sha256']:
            raise ValueError(f'Canonical file changed: {target}')
        if action['kind'] == 'move_unique':
            destination = target
        else:
            destination = archive / 'originals' / source.relative_to(SUBJECT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError(f'Refusing overwrite: {destination}')
        source.rename(destination)
        if digest(destination) != action['sha256']:
            raise ValueError(f'Hash mismatch: {destination}')

    def rewrite_link(match: re.Match[str]) -> str:
        path, suffix = match[1], match[2] or ''
        decoded = unquote(path)
        if decoded.startswith('Lora/05 University/'):
            decoded = decoded.removeprefix('Lora/')
        replacement = aliases.get(decoded, decoded)
        if replacement != path:
            return f'[[{replacement}{suffix}]]'
        return match[0]

    updated = 0
    for note in sorted(SUBJECT.rglob('*.md')):
        if 'excalidraw' in note.name.casefold() or 'drawing' in note.name.casefold():
            continue
        previous = note.read_text(encoding='utf-8')
        current = re.sub(r'\[\[([^\]|]+)(\|[^\]]*)?\]\]', rewrite_link, previous)
        if current != previous:
            backup = archive / 'before-link-updates' / note.relative_to(SUBJECT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(note, backup)
            note.write_text(current, encoding='utf-8')
            updated += 1
    # Only now remove verified empty old containers, keeping all contents in the manifest.
    for folder in folders:
        for child in sorted(folder.rglob('*'), key=lambda path: len(path.parts), reverse=True):
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()
        if not any(folder.iterdir()):
            folder.rmdir()
    for action in actions:
        target = Path(action['target'])
        if not target.is_file() or Path(action['source']).exists():
            raise ValueError(f'Incomplete migration: {action}')
        if action['kind'] != 'archive_legacy_note' and target.suffix != '.md':
            if digest(target) != action['sha256']:
                raise ValueError(f'Canonical mismatch: {target}')
    print(json.dumps({'archive': str(archive), 'links_updated_in_notes': updated,
                      'verified_actions': len(actions)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    actions, aliases, folders = plan()
    print(json.dumps({'actions': dict(Counter(action['kind'] for action in actions)),
                      'old_folders': len(folders), 'sources': [action['source'].removeprefix(str(SUBJECT) + '/')
                                                            for action in actions if action['kind'] == 'move_unique']}, ensure_ascii=False))
    if args.apply and actions:
        apply(actions, aliases, folders)


if __name__ == '__main__':
    main()
