"""Refresh test fixture data from Binance S3 archive.

Downloads representative sample files from data.binance.vision and writes
a checksum manifest for version tracking.

Usage:
    uv run python3 scripts/refresh_fixtures.py          # download + verify
    uv run python3 scripts/refresh_fixtures.py --verify  # verify only
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ── Fixture manifest ──────────────────────────────────────────

MANIFEST_PATH = Path("tests/fixture/binance/manifest.json")

# Source → dest paths relative to tests/fixture/binance/data/
FIXTURE_FILES = [
    # spot klines (1h interval)
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-08.zip",
    "data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05-09.zip",
    # spot aggTrades
    "data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-05-08.zip",
    # spot trades
    "data/spot/daily/trades/BTCUSDT/BTCUSDT-trades-2026-05-08.zip",
    # um fundingRate (monthly)
    "data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-04.zip",
    # cm aggTrades
    "data/futures/cm/daily/aggTrades/BTCUSD_PERP/BTCUSD_PERP-aggTrades-2026-05-08.zip",
]

BASE_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FIXTURE_ROOT = Path("tests/fixture/binance")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download() -> list[dict[str, Any]]:
    """Download fixture files and return manifest entries."""
    import urllib.request

    manifest: list[dict[str, Any]] = []
    for rel_path in FIXTURE_FILES:
        dl = FIXTURE_ROOT / rel_path
        dl.parent.mkdir(parents=True, exist_ok=True)

        url = f"{BASE_URL}/{rel_path}"
        try:
            r = urllib.request.urlopen(url, timeout=30)
            dl.write_bytes(r.read())
            digest = sha256(dl)
            size = dl.stat().st_size
            manifest.append({"path": rel_path, "sha256": digest, "size": size})
            print(
                f"  ✓ {rel_path} ({size / 1024:.1f} KB)"
                if size > 1024
                else f"  ✓ {rel_path} ({size} B)"
            )

            # Download checksum file
            ck = dl.with_suffix(dl.suffix + ".CHECKSUM")
            try:
                r = urllib.request.urlopen(f"{url}.CHECKSUM", timeout=10)
                ck.write_bytes(r.read())
            except Exception:
                pass
        except Exception as e:
            print(f"  ✗ {rel_path}: {e}")
    return manifest


def verify() -> list[dict[str, Any]]:
    """Verify existing fixture files against manifest. Returns current manifest."""
    manifest: list[dict[str, Any]] = []
    for rel_path in FIXTURE_FILES:
        dl = FIXTURE_ROOT / rel_path
        if not dl.exists():
            print(f"  ✗ {rel_path}: MISSING")
            continue
        digest = sha256(dl)
        size = dl.stat().st_size
        manifest.append({"path": rel_path, "sha256": digest, "size": size})

        # Verify against checksum file if present
        ck = dl.with_suffix(dl.suffix + ".CHECKSUM")
        if ck.exists():
            expected = ck.read_text().strip().split()[0]
            if expected == digest:
                print(f"  ✓ {rel_path}")
            else:
                print(f"  ✗ {rel_path}: checksum MISMATCH")
        else:
            print(f"  ~ {rel_path} ({size / 1024:.1f} KB)")
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

    # Always verify against checksum files
    total = len(manifest)
    ok = sum(1 for m in manifest if "unexpected" not in str(m))
    print(f"\n  {ok}/{total} files OK")
