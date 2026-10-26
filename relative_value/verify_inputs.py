"""Verify the processed public-data snapshot used by the published research."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent

def main():
    manifest = json.loads((ROOT / 'INPUT_SNAPSHOT.json').read_text())
    failures = []
    for item in manifest['files']:
        path = ROOT / item['path']
        if not path.is_file():
            failures.append(item['path'] + ': missing')
        elif path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            failures.append(item['path'] + ': differs from snapshot')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f"Verified {len(manifest['files'])} input files against the published snapshot.")

if __name__ == '__main__':
    main()
