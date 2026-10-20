"""Private backups of both migration source and active v2 data, without shell env parsing."""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    root = Path(__file__).resolve().parents[1] / 'backups'
    root.mkdir(mode=0o700, exist_ok=True)
    binary = shutil.which('pg_dump') or '/opt/homebrew/opt/postgresql@17/bin/pg_dump'
    restore = str(Path(binary).with_name('pg_restore'))
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for label, key in (('legacy', 'DATABASE_URL'), ('v2', 'LORA_V2_DATABASE_URL')):
        value = os.getenv(key)
        if not value:
            raise ValueError(key + ' is not configured')
        url = urlsplit(value)
        env = dict(os.environ, PGHOST=url.hostname or 'localhost', PGPORT=str(url.port or 5432),
                   PGDATABASE=unquote(url.path.lstrip('/')), PGUSER=unquote(url.username or ''),
                   PGPASSWORD=unquote(url.password or ''))
        target = root / ('lora_' + label + '_' + stamp + '.dump')
        temporary = target.with_suffix('.dump.tmp')
        temporary.touch(mode=0o600)
        try:
            result = subprocess.run([binary, '--format=custom', '--no-owner', '--no-acl', '--file', str(temporary)], env=env, capture_output=True)
            if result.returncode:
                raise RuntimeError('Backup failed for ' + label)
            result = subprocess.run([restore, '--list', str(temporary)], capture_output=True)
            if result.returncode or not temporary.stat().st_size:
                raise RuntimeError('Backup validation failed for ' + label)
            temporary.replace(target)
            print('Backup verified:', target.name)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
