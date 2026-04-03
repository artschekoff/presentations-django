"""List S3 folders containing PDF files smaller than 1 MB."""

import os
import time
import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "preza.kz").strip('"')
PREFIX = os.getenv("S3_PREFIX", "").strip('"')
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.ru-3.storage.selcloud.ru").strip('"')
REGION = os.getenv("S3_REGION", "ru-3").strip('"')
MAX_PDF_SIZE = 1_048_576  # 1 MB
OUTPUT_FILE = "s3-small-pdf.txt"


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

    folders: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    total_objects = 0
    total_pdfs = 0
    pages = 0
    start = time.time()

    print("Scanning objects...")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        pages += 1
        contents = page.get("Contents", [])
        total_objects += len(contents)
        for obj in contents:
            key = obj["Key"]
            size = obj["Size"]
            if key.endswith(".pdf"):
                total_pdfs += 1
                if size < MAX_PDF_SIZE:
                    folder = key.rsplit("/", 1)[0] if "/" in key else ""
                    if folder:
                        folders.add(folder)
        print(f"  page {pages}: {total_objects} objects scanned, "
              f"{total_pdfs} PDFs found, {len(folders)} small-pdf folders so far")

    elapsed = time.time() - start
    result = sorted(folders)

    print(f"\nScan complete in {elapsed:.1f}s")
    print(f"  Total objects: {total_objects}")
    print(f"  Total PDFs: {total_pdfs}")
    print(f"  PDFs < 1MB: {len(result)} folders")

    with open(OUTPUT_FILE, "w") as f:
        for folder in result:
            f.write(folder + "\n")

    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
