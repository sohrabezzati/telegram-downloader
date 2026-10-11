#!/usr/bin/env python3
"""Audit Git-visible files without printing secret values or reading ignored files."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = {'telegram.properties', 'key.properties', 'credentials.json', 'secrets.json'}
PRIVATE_SUFFIXES = ('.jks', '.keystore', '.p12', '.pfx', '.session', '.session-journal', '.session-wal', '.session-shm', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.apk', '.aab')
PATTERNS = {
    'literal bot token': re.compile(rb'(?<![\w-])[0-9]{6,15}:[A-Za-z0-9_-]{25,}(?![\w-])'),
    'literal API hash': re.compile(rb'''(?im)\b(?:api_hash|apiHash)\b\s*[:=]\s*['"]?([a-fA-F0-9]{32})(?![a-fA-F0-9])'''),
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
}

def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).split(b'\0')
    findings = []
    count = 0
    for raw in sorted(set(paths)):
        if not raw:
            continue
        relative = raw.decode('utf-8', errors='surrogateescape')
        path = ROOT / relative
        if not path.is_file():
            continue
        count += 1
        name = path.name
        if name in PRIVATE_NAMES or name.endswith(PRIVATE_SUFFIXES) or (name.startswith('.env') and name != '.env.example'):
            findings.append((relative, 'private file is visible to Git'))
            continue
        if path.stat().st_size > 10_000_000:
            findings.append((relative, 'large file requires manual review'))
            continue
        data = path.read_bytes()
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append((relative, label))
    if findings:
        for path, reason in findings:
            print(f'{path}: {reason}')
        print('Sensitive-file audit failed. Values were not printed.')
        return 1
    print(f'Sensitive-file audit passed for {count} Git-visible files. Ignored private files were not read.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
