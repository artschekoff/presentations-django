"""List S3 folders that contain all three file types: .pdf, .txt, .pptx."""

import os
import time
from collections import defaultdict
import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "preza.kz").strip('"')
PREFIX = os.getenv("S3_PREFIX", "").strip('"')
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.ru-3.storage.selcloud.ru").strip('"')
REGION = os.getenv("S3_REGION", "ru-3").strip('"')
REQUIRED_EXTS = {".pdf", ".txt", ".pptx"}
OUTPUT_FILE = "s3-complete.txt"


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

    folder_exts: dict[str, set[str]] = defaultdict(set)
    paginator = s3.get_paginator("list_objects_v2")
    total_objects = 0
    pages = 0
    start = time.time()

    print("Scanning objects...")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        pages += 1
        contents = page.get("Contents", [])
        total_objects += len(contents)
        for obj in contents:
            key = obj["Key"]
            if "/" not in key:
                continue
            folder = key.rsplit("/", 1)[0]
            filename = key.rsplit("/", 1)[1]
            dot = filename.rfind(".")
            if dot != -1:
                ext = filename[dot:].lower()
                if ext in REQUIRED_EXTS:
                    folder_exts[folder].add(ext)

        complete_so_far = sum(1 for exts in folder_exts.values() if exts >= REQUIRED_EXTS)
        print(f"  page {pages}: {total_objects} objects scanned, "
              f"{len(folder_exts)} folders seen, {complete_so_far} complete")

    elapsed = time.time() - start
    result = sorted(f for f, exts in folder_exts.items() if exts >= REQUIRED_EXTS)
    incomplete = len(folder_exts) - len(result)

    print(f"\nScan complete in {elapsed:.1f}s")
    print(f"  Total objects: {total_objects}")
    print(f"  Total folders: {len(folder_exts)}")
    print(f"  Complete (pdf+txt+pptx): {len(result)}")
    print(f"  Incomplete: {incomplete}")

    with open(OUTPUT_FILE, "w") as f:
        for folder in result:
            f.write(folder + "\n")

    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
