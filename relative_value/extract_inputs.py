"""Reassemble and verify the published input archive, then safely extract it."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    spec = json.loads((ROOT / 'inputs' / 'ARCHIVE.json').read_text())
    archive = ROOT / 'research-inputs.zip'
    if not archive.exists() or digest(archive) != spec['sha256']:
        temp = archive.with_suffix('.building.zip')
        try:
            with temp.open('wb') as out:
                for part in spec['parts']:
                    source = ROOT / 'inputs' / part['name']
                    if source.stat().st_size != part['bytes'] or digest(source) != part['sha256']:
                        raise ValueError('Archive part failed verification: ' + part['name'])
                    with source.open('rb') as stream:
                        shutil.copyfileobj(stream, out)
            if temp.stat().st_size != spec['bytes'] or digest(temp) != spec['sha256']:
                raise ValueError('Reassembled archive failed verification')
            os.replace(temp, archive)
        finally:
            temp.unlink(missing_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            destination = (ROOT / entry.filename).resolve()
            if not destination.is_relative_to(ROOT):
                raise ValueError('Unsafe archive member: ' + entry.filename)
        failed = bundle.testzip()
        if failed:
            raise ValueError('Corrupted archive member: ' + failed)
        bundle.extractall(ROOT)
        print(f'Extracted {len(bundle.infolist())} verified input files.')


if __name__ == '__main__':
    main()
