import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "dependency_sources", Path(__file__).parents[1] / "scripts/prepare_dependency_sources.py"
)
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


def test_source_hash_failure_preserves_cache_and_removes_partial_download(tmp_path):
    target = tmp_path / "source.tar.xz"
    target.write_bytes(b"previous archive")
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"corrupt archive")
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            sources.download(client, "https://example.org/source", target, "0" * 64)
    assert target.read_bytes() == b"previous archive"
    assert not target.with_suffix(".xz.part").exists()


def test_verified_source_download_is_reused_without_network(tmp_path):
    target = tmp_path / "source.tar.xz"
    target.write_bytes(b"verified source")
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    sources.download(None, "https://example.org/source", target, checksum)


def test_notice_extraction_rejects_traversal(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as bundle:
        item = tarfile.TarInfo("module/../../LICENSE.txt")
        item.size = 7
        bundle.addfile(item, io.BytesIO(b"license"))
    with pytest.raises(RuntimeError, match="Invalid source notice path"):
        sources.collect_notices(archive, tmp_path / "notices")
    assert not (tmp_path / "LICENSE.txt").exists()
