#!/usr/bin/env python3
"""Download one HTTP(S) file with proxy support, resume, and integrity checks."""

from __future__ import annotations

import argparse
import hashlib
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def opener(proxy: str | None) -> urllib.request.OpenerDirector:
    if not proxy:
        return urllib.request.build_opener()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def download(
    url: str,
    destination: Path,
    expected_bytes: int,
    expected_md5: str,
    retries: int,
    timeout: int,
    proxy: str | None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")

    if destination.exists() and destination.stat().st_size == expected_bytes:
        actual_md5 = md5_file(destination)
        if actual_md5 == expected_md5.lower():
            print(f"skipped_verified: {destination}")
            return

    last_error = ""
    for attempt in range(1, retries + 1):
        offset = part.stat().st_size if part.exists() else 0
        if offset > expected_bytes:
            raise RuntimeError(
                f"partial file is larger than expected: {offset} > {expected_bytes}"
            )
        if offset == expected_bytes:
            actual_md5 = md5_file(part)
            if actual_md5 != expected_md5.lower():
                raise RuntimeError(
                    f"completed partial file failed md5: expected {expected_md5}, "
                    f"got {actual_md5}"
                )
            part.replace(destination)
            print(f"downloaded: {destination}")
            return

        headers = {"Range": f"bytes={offset}-"} if offset else {}
        request = urllib.request.Request(url, headers=headers)
        try:
            with opener(proxy).open(request, timeout=timeout) as response:
                if offset and response.status != 206:
                    raise RuntimeError(
                        f"server did not honor resume at byte {offset}: "
                        f"HTTP {response.status}"
                    )
                mode = "ab" if offset and response.status == 206 else "wb"
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            last_error = str(exc)
            print(
                f"attempt {attempt}/{retries} interrupted at "
                f"{part.stat().st_size if part.exists() else 0} bytes: {exc}",
                flush=True,
            )
            if attempt < retries:
                time.sleep(min(30, 3 * attempt))
            continue

        actual_bytes = part.stat().st_size if part.exists() else 0
        if actual_bytes != expected_bytes:
            last_error = f"size mismatch: expected {expected_bytes}, got {actual_bytes}"
            print(
                f"attempt {attempt}/{retries} incomplete: {last_error}",
                flush=True,
            )
            if attempt < retries:
                time.sleep(min(30, 3 * attempt))
            continue

        actual_md5 = md5_file(part)
        if actual_md5 != expected_md5.lower():
            raise RuntimeError(
                f"md5 mismatch: expected {expected_md5}, got {actual_md5}"
            )
        part.replace(destination)
        print(f"downloaded: {destination}")
        return

    raise RuntimeError(last_error or "download failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-md5", required=True)
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--proxy",
        default=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
    )
    args = parser.parse_args()

    download(
        args.url,
        args.destination.resolve(),
        args.expected_bytes,
        args.expected_md5,
        args.retries,
        args.timeout,
        args.proxy,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
