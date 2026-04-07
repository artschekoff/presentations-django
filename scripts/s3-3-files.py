#!/usr/bin/env python3
"""List S3 folders with fewer than 3 files among .txt, .pdf, .pptx (only these count)."""

import os
import time
import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "preza.kz").strip('"')
PREFIX = os.getenv("S3_PREFIX", "").strip('"')
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.ru-3.storage.selcloud.ru").strip('"')
REGION = os.getenv("S3_REGION", "ru-3").strip('"')
COUNTED_EXTENSIONS = frozenset({"txt", "pdf", "pptx"})
MIN_FILES = 3
OUTPUT_FILE = "s3-fewer-than-3-files.txt"


def folder_for_key(key: str) -> str | None:
    if "/" not in key:
        return None
    return key.rsplit("/", 1)[0]


def counted_ext(key: str) -> str | None:
    name = key.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    return ext if ext in COUNTED_EXTENSIONS else None


def main():
    print(f"Connecting to S3: bucket={BUCKET}, endpoint={ENDPOINT_URL}")
    s3 = boto3.client(
        "s3",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "").strip('"'),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "").strip('"'),
        verify=os.getenv("S3_VERIFY_SSL", "true").lower() not in ("false", "0", "no"),
    )

    # folder -> count of .txt/.pdf/.pptx only
    counts: dict[str, int] = {}
    paginator = s3.get_paginator("list_objects_v2")
    total_objects = 0
    matched = 0
    pages = 0
    start = time.time()

    print(
        f"Scanning objects (counting only {', '.join(sorted(COUNTED_EXTENSIONS))}; "
        f"folders with < {MIN_FILES} such files)..."
    )
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        pages += 1
        contents = page.get("Contents", [])
        total_objects += len(contents)
        for obj in contents:
            key = obj["Key"]
            if key.endswith("/"):
                continue
            if counted_ext(key) is None:
                continue
            matched += 1
            folder = folder_for_key(key)
            if folder is None:
                continue
            counts[folder] = counts.get(folder, 0) + 1
        print(
            f"  page {pages}: {total_objects} objects scanned, "
            f"{matched} txt/pdf/pptx, {len(counts)} folders with any such file"
        )

    sparse = sorted(f for f, n in counts.items() if n < MIN_FILES)

    elapsed = time.time() - start
    print(f"\nScan complete in {elapsed:.1f}s")
    print(f"  Total objects: {total_objects}")
    print(f"  txt/pdf/pptx files: {matched}")
    print(f"  Folders with < {MIN_FILES} such files: {len(sparse)}")

    with open(OUTPUT_FILE, "w") as f:
        for folder in sparse:
            f.write(folder + "\n")

    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
