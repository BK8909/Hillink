"""CL-1025-36d — 시험 전용 지원(운영 모듈 approval_sidecar_qa 에는 매니페스트 주입 경로가 없음).
합성 입력은 이 하위 클래스로만 다른 매니페스트를 쓸 수 있다. 운영 진입점은 approval_sidecar_qa.TrustedInputs(boundary, approval, source_dir)."""
import hashlib
from pathlib import Path
import approval_sidecar_qa as S


def test_manifest(b, a, src):
    h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return dict(boundary_csv=h(b), approval_csv=h(a), source_facts={p.parent.parent.name: h(p) for p in Path(src).glob("WH-*/candidate/facts_events_evidence.json")})


class TestOnlyTrustedInputs(S.TrustedInputs):
    __test__ = False

    def __init__(self, boundary_csv, approval_csv, source_dir, manifest):
        self._test_manifest = manifest
        super().__init__(boundary_csv, approval_csv, source_dir)

    def _manifest(self):
        return S._check_manifest(self._test_manifest)


def bind_of(manifest):
    return S.sha_of(manifest)
