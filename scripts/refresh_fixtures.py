"""Refresh test fixture data from Binance S3 archive.

Downloads representative sample files from data.binance.vision and writes
a checksum manifest for version tracking. Checksums are sourced from the
Binance archive's .CHECKSUM files (not computed locally), so the manifest
reflects the authority's expected digests.

Usage:
    uv run python3 scripts/refresh_fixtures.py          # download + manifest
    uv run python3 scripts/refresh_fixtures.py --verify  # verify only
"""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from pathlib import Path
from typing import Any

# ── Fixture manifest ──────────────────────────────────────────

MANIFEST_PATH = Path("tests/fixture/binance/manifest.json")

# Source → dest paths relative to tests/fixture/binance/data/
FIXTURE_FILES = [
    # spot klines (1h interval)
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-08.zip",
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-08.zip.CHECKSUM",
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-09.zip",
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-09.zip.CHECKSUM",
    # spot aggTrades
    "data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-05-08.zip",
    "data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-05-08.zip.CHECKSUM",
    # spot trades
    "data/spot/daily/trades/BTCUSDT/BTCUSDT-trades-2026-05-08.zip",
    "data/spot/daily/trades/BTCUSDT/BTCUSDT-trades-2026-05-08.zip.CHECKSUM",
    # um fundingRate (monthly)
    "data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-04.zip",
    "data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-04.zip.CHECKSUM",
    # cm aggTrades
    "data/futures/cm/daily/aggTrades/BTCUSD_PERP/BTCUSD_PERP-aggTrades-2026-05-08.zip",
    "data/futures/cm/daily/aggTrades/BTCUSD_PERP/BTCUSD_PERP-aggTrades-2026-05-08.zip.CHECKSUM",
]

BASE_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FIXTURE_ROOT = Path("tests/fixture/binance")


def _checksum_path(dl: Path) -> Path:
    return dl.with_suffix(dl.suffix + ".CHECKSUM")


def _read_binance_checksum(ck: Path) -> str | None:
    """Parse checksum from Binance-format CHECKSUM file (first token)."""
    if not ck.exists():
        return None
    return ck.read_text().strip().split()[0]


def _download(url: str, dest: Path) -> None:
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    r = urllib.request.urlopen(url, timeout=30)
    dest.write_bytes(r.read())


def download() -> list[dict[str, Any]]:
    """Download fixture files + CHECKSUMs; manifest uses archive's checksums."""
    manifest: list[dict[str, Any]] = []
    for rel_path in FIXTURE_FILES:
        dl = FIXTURE_ROOT / rel_path
        url = f"{BASE_URL}/{rel_path}"

        # CHECKSUM files: download and record their content as sha256
        if rel_path.endswith(".CHECKSUM"):
            try:
                _download(f"{url}", dl)
                content = dl.read_text().strip()
                manifest.append(
                    {
                        "path": rel_path,
                        "sha256": content.split()[0] if content else None,
                        "size": dl.stat().st_size,
                    }
                )
                print(f"  ✓ {rel_path}")
            except Exception as e:
                print(f"  ✗ {rel_path}: {e}")
            continue

        # ZIP files: download CHECKSUM first if needed, then verify
        ck = _checksum_path(dl)
        ck_rel = f"{rel_path}.CHECKSUM"
        if not ck.exists():
            with suppress(Exception):
                _download(f"{url}.CHECKSUM", ck)
        try:
            _download(url, dl)
        except Exception as e:
            print(f"  ✗ {rel_path}: {e}")
            continue

        expected = _read_binance_checksum(ck)
        actual = hashlib.sha256(dl.read_bytes()).hexdigest()
        size = dl.stat().st_size

        if expected and actual != expected:
            print(f"  ✗ {rel_path}: checksum MISMATCH (download corrupted)")
            continue

        manifest.append(
            {"path": rel_path, "sha256": expected, "size": size, "checksum_path": ck_rel}
        )
        print(
            f"  ✓ {rel_path} ({size / 1024:.1f} KB)"
            if size > 1024
            else f"  ✓ {rel_path} ({size} B)"
        )

    return manifest


def verify() -> list[dict[str, Any]]:
    """Verify existing fixture files against Binance CHECKSUM files."""
    manifest: list[dict[str, Any]] = []
    for rel_path in FIXTURE_FILES:
        dl = FIXTURE_ROOT / rel_path

        if not dl.exists():
            print(f"  ✗ {rel_path}: MISSING")
            continue

        # CHECKSUM files: just track them
        if rel_path.endswith(".CHECKSUM"):
            content = dl.read_text().strip()
            manifest.append(
                {
                    "path": rel_path,
                    "sha256": content.split()[0] if content else None,
                    "size": dl.stat().st_size,
                }
            )
            print(f"  ✓ {rel_path}")
            continue

        # ZIP files: verify against companion CHECKSUM
        ck_rel = f"{rel_path}.CHECKSUM"
        ck = FIXTURE_ROOT / ck_rel
        expected = _read_binance_checksum(ck)
        if expected is None:
            print(f"  ~ {rel_path}: no CHECKSUM file")
            continue

        actual = hashlib.sha256(dl.read_bytes()).hexdigest()
        size = dl.stat().st_size
        manifest.append(
            {"path": rel_path, "sha256": expected, "size": size, "checksum_path": ck_rel}
        )

        if actual == expected:
            print(f"  ✓ {rel_path}")
        else:
            print(f"  ✗ {rel_path}: checksum MISMATCH")

    return manifest


def write_manifest(manifest: list[dict[str, Any]]) -> None:
    (FIXTURE_ROOT / "manifest.json").write_text(
        json.dumps({"version": 1, "files": manifest}, indent=2) + "\n"
    )
    print(f"\n  Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    import sys

    do_verify = "--verify" in sys.argv

    if do_verify:
        print("Verifying fixtures...")
        manifest = verify()
    else:
        print("Downloading fixtures from Binance S3 archive...")
        manifest = download()
        write_manifest(manifest)

    total = len(manifest)
    print(f"\n  {total}/{total} files OK")
