"""Delete S3 objects filtered by extension(s). Pass extensions as arguments.

Usage:
    python scripts/s3_rm_by_ext.py .txt          # delete all .txt files
    python scripts/s3_rm_by_ext.py .png .txt      # delete all .png and .txt files
    python scripts/s3_rm_by_ext.py --all          # delete everything
"""

import os
import sys
import time
import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "preza.kz").strip('"')
PREFIX = os.getenv("S3_PREFIX", "").strip('"')
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.ru-3.storage.selcloud.ru").strip('"')
REGION = os.getenv("S3_REGION", "ru-3").strip('"')
BATCH_SIZE = 1000


def build_client():
    return boto3.client(
        "s3",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "").strip('"'),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "").strip('"'),
        verify=os.getenv("S3_VERIFY_SSL", "true").lower() not in ("false", "0", "no"),
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    delete_all = "--all" in sys.argv
    extensions = tuple(a.lower() for a in sys.argv[1:] if not a.startswith("-"))

    if not delete_all and not extensions:
        print("Provide at least one extension or --all")
        sys.exit(1)

    target = "ALL objects" if delete_all else f"*{' *'.join(extensions)} files"
    print(f"Target: {target}")
    print(f"Connecting to S3: bucket={BUCKET}, endpoint={ENDPOINT_URL}")

    s3 = build_client()
    paginator = s3.get_paginator("list_objects_v2")

    to_delete: list[dict] = []
    total_scanned = 0
    total_matched = 0
    total_deleted = 0
    pages = 0
    start = time.time()

    print("Scanning objects...")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        pages += 1
        contents = page.get("Contents", [])
        total_scanned += len(contents)

        for obj in contents:
            key = obj["Key"]
            if delete_all or key.lower().endswith(extensions):
                total_matched += 1
                to_delete.append({"Key": key})

            if len(to_delete) >= BATCH_SIZE:
                s3.delete_objects(Bucket=BUCKET, Delete={"Objects": to_delete})
                total_deleted += len(to_delete)
                to_delete.clear()
                elapsed = time.time() - start
                print(f"  {total_deleted} deleted / {total_scanned} scanned ({elapsed:.1f}s)")

        print(f"  page {pages}: {total_scanned} scanned, {total_matched} matched")

    if to_delete:
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": to_delete})
        total_deleted += len(to_delete)

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Scanned: {total_scanned}")
    print(f"  Matched: {total_matched}")
    print(f"  Deleted: {total_deleted}")


if __name__ == "__main__":
    main()
