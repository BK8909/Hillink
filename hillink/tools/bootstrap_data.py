"""Restore the data committed with this branch; no external input delivery is needed."""
import argparse, errno, hashlib, json, os, shutil, tarfile, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def restore_display_review(spec, target):
    """Resolve SHA-bound display sources without touching runtime profiles."""
    ref = spec.get('profile_display_review')
    if not ref:
        return None
    data = (ROOT / 'handover/data').resolve()
    manifest = (data / ref['path']).resolve()
    if data not in manifest.parents or sha(manifest) != ref['sha256']:
        raise ValueError('DISPLAY_REVIEW_MANIFEST_SHA_MISMATCH')
    review = json.loads(manifest.read_text())
    for pid, row in review['customers'].items():
        for anchor in row['source_anchors']:
            if anchor.get('customer_id') != pid:
                raise ValueError('DISPLAY_REVIEW_CUSTOMER_MISMATCH')
            bundled = 'bundle_path' in anchor
            base = target.resolve() if bundled else data
            path = (base / anchor['bundle_path' if bundled else 'supplemental_path']).resolve()
            if base not in path.parents or sha(path) != anchor['sha256']:
                raise ValueError('DISPLAY_REVIEW_SOURCE_SHA_MISMATCH')
            if bundled:
                posts = json.loads(path.read_text())
                if not all(post.startswith(pid + '_') and any(p.get('post_id') == post for p in posts)
                           for post in row['post_ids']):
                    raise ValueError('DISPLAY_REVIEW_POST_CUSTOMER_MISMATCH')
            elif path.name.endswith('-display-evidence.json'):
                evidence = json.loads(path.read_text())
                if evidence.get('customer_id') != pid or not set(row['post_ids']).issubset({p['post_id'] for p in evidence['posts']}):
                    raise ValueError('DISPLAY_REVIEW_POST_CUSTOMER_MISMATCH')
            anchor['path'] = str(path)
    from connect_private_data import publish
    destination = target / ('display-review-' + ref['sha256'] + '.runtime.json')
    publish(destination, json.dumps(review, ensure_ascii=False, indent=2).encode())
    return str(destination)


def bootstrap():
    spec = json.loads((ROOT / 'handover/data/bundle.json').read_text())
    archive = ROOT / 'handover/data' / spec['archive']
    if sha(archive) != spec['sha256']:
        raise ValueError('BUNDLED_DATA_ARCHIVE_SHA_MISMATCH')
    for row in spec.get('supplemental_files',[]):
        path=(ROOT/'handover/data'/row['path']).resolve()
        if (ROOT/'handover/data').resolve() not in path.parents or sha(path)!=row['sha256']:
            raise ValueError('SUPPLEMENTAL_DATA_SHA_MISMATCH')
    parent = Path(os.environ.get('HILLINK_DATA_HOME', Path.home() / '.cache/hillink/data')).resolve()
    if any((p / '.git').exists() for p in (parent, *parent.parents)):
        raise ValueError('RUNTIME_DATA_CACHE_MUST_BE_OUTSIDE_GIT')
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = parent / spec['sha256']
    if not target.exists():
        staging = Path(tempfile.mkdtemp(prefix='.restore-', dir=parent))
        try:
            seen = set()
            with tarfile.open(archive, 'r:gz') as package:
                total = 0
                for member in package:
                    destination = (staging / member.name).resolve()
                    if not member.isfile() or staging not in destination.parents or member.name in seen:
                        raise ValueError('UNSAFE_BUNDLED_DATA_ENTRY')
                    seen.add(member.name)
                    total += member.size
                    if total > spec['uncompressed_bytes']:
                        raise ValueError('BUNDLED_DATA_SIZE_MISMATCH')
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with package.extractfile(member) as source, destination.open('xb') as output:
                        shutil.copyfileobj(source, output)
                    destination.chmod(0o600)
                if total != spec['uncompressed_bytes'] or len(seen) != spec['files']:
                    raise ValueError('BUNDLED_DATA_INCOMPLETE')
            try:
                staging.rename(target)
            except OSError as exc:
                # macOS reports an already-published nonempty directory as
                # ENOTEMPTY; Linux may report EEXIST. Validate the winner below.
                if exc.errno not in (errno.EEXIST,errno.ENOTEMPTY) or not target.is_dir():raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    if sha(target/'manifest.json') != spec['manifest_sha256']:
        raise ValueError('BUNDLED_DATA_MANIFEST_SHA_MISMATCH')
    import connect_private_data
    registry = connect_private_data.connect(target)
    return {'path': str(registry), 'sha256': sha(registry), 'bundle_sha256': spec['sha256'],
            'profile_display_review': restore_display_review(spec, target)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = bootstrap()
    print(json.dumps(result))
