"""Batch-update presentations status to 'queued' for task_ids from s3-small-pdf.txt."""

import os
import time
import psycopg2
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE = 20
INPUT_FILE = "s3-small-pdf.txt"
NEW_STATUS = "queued"


def main():
    with open(INPUT_FILE) as f:
        task_ids = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(task_ids)} task_ids from {INPUT_FILE}")
    total_batches = (len(task_ids) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Batch size: {BATCH_SIZE}, total batches: {total_batches}")

    db_host = os.getenv("DJANGO_DB_HOST")
    db_port = os.getenv("DJANGO_DB_PORT")
    db_name = os.getenv("DJANGO_DB_NAME")
    print(f"Connecting to PostgreSQL: {db_host}:{db_port}/{db_name}")

    conn = psycopg2.connect(
        dbname=db_name,
        user=os.getenv("DJANGO_DB_USER"),
        password=os.getenv("DJANGO_DB_PASSWORD"),
        host=db_host,
        port=db_port,
    )
    print("Connected.")

    total_updated = 0
    start = time.time()

    try:
        with conn:
            with conn.cursor() as cur:
                for i in range(0, len(task_ids), BATCH_SIZE):
                    batch = task_ids[i : i + BATCH_SIZE]
                    batch_num = i // BATCH_SIZE + 1
                    placeholders = ",".join(["%s"] * len(batch))
                    cur.execute(
                        f"UPDATE presentations_app_presentation "
                        f"SET status = %s "
                        f"WHERE task_id IN ({placeholders})",
                        [NEW_STATUS, *batch],
                    )
                    total_updated += cur.rowcount
                    elapsed = time.time() - start
                    print(f"  batch {batch_num}/{total_batches}: "
                          f"{len(batch)} ids → {cur.rowcount} rows updated "
                          f"({total_updated} total, {elapsed:.1f}s)")
    finally:
        conn.close()
        print("Connection closed.")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s. Total rows updated: {total_updated}/{len(task_ids)}")


if __name__ == "__main__":
    main()
