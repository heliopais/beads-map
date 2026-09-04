#!/usr/bin/env python3
"""Normalize an sdist container so repeated builds are byte-identical."""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
from pathlib import Path
import tarfile


def normalize_sdist(path: Path, mtime: int) -> None:
    with tarfile.open(path, "r:gz") as source:
        entries = []
        for member in source:
            extracted = source.extractfile(member) if member.isfile() else None
            entries.append((copy.copy(member), extracted.read() if extracted else None))

    temporary = path.with_name(f".{path.name}.normalized")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw,
            mtime=mtime,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.USTAR_FORMAT,
            ) as target:
                for member, data in entries:
                    member.uid = 0
                    member.gid = 0
                    member.uname = ""
                    member.gname = ""
                    member.mtime = mtime
                    member.pax_headers = {}
                    target.addfile(member, io.BytesIO(data) if data is not None else None)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdist", type=Path)
    parser.add_argument("mtime", type=int)
    args = parser.parse_args()
    normalize_sdist(args.sdist, args.mtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
