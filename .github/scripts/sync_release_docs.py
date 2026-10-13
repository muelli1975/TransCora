"""Sync release documents while keeping tested program files byte-identical."""
from pathlib import Path
import hashlib
import io
import json
import os
import shutil
import tarfile
import zipfile

def sync_archive(archive, documents):
    replacements = {'TransCora/source/'+name: Path(name).read_bytes() for name in documents}
    replacements.update({'TransCora/'+name: Path(name).read_bytes()
                         for name in documents if '/' not in name})
    manifest_name = 'TransCora/BUILD_HASHES.json'
    if archive.suffix == '.zip':
        with zipfile.ZipFile(archive) as source:
            manifest = json.loads(source.read(manifest_name))
            members = set(source.namelist())
    else:
        with tarfile.open(archive, 'r:gz') as source:
            manifest = json.load(source.extractfile(manifest_name))
            members = set(source.getnames())
    assert set(replacements) <= members, 'A package document is missing'
    for name, data in replacements.items():
        key = name.removeprefix('TransCora/')
        assert key in manifest, 'Document missing from build manifest'
        manifest[key] = hashlib.sha256(data).hexdigest()
    replacements[manifest_name] = json.dumps(manifest, indent=2).encode()
    temporary = archive.with_name('sync-'+archive.name)
    try:
        if archive.suffix == '.zip':
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(temporary, 'w') as target:
                for member in source.infolist():
                    if member.filename in replacements:
                        target.writestr(member, replacements[member.filename])
                    else:
                        with source.open(member) as original, target.open(member, 'w', force_zip64=True) as destination:
                            shutil.copyfileobj(original, destination, 1024*1024)
        else:
            with tarfile.open(archive, 'r:gz') as source, tarfile.open(temporary, 'w:gz') as target:
                for member in source:
                    if member.name in replacements:
                        data = replacements[member.name]
                        member.size = len(data)
                        target.addfile(member, io.BytesIO(data))
                    else:
                        target.addfile(member, source.extractfile(member) if member.isfile() else None)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_name(archive.name+'.sha256').write_text(digest+'  '+archive.name+'\n')

if __name__ == '__main__':
    documents = os.environ['DOC_PATHS'].split()
    folder = Path('release-files')
    archives = list(folder.glob('*.zip'))+list(folder.glob('*.tar.gz'))
    assert len(archives) == 3
    for archive in archives:
        sync_archive(archive, documents)
        print('Synced documentation:', archive.name)
