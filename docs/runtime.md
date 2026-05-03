# Runtime configuration

Copy `.env.example` → `.env`.

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret |
| `DJANGO_DB_*` | PostgreSQL connection |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis URLs |
| `CHANNEL_REDIS_URL` | Django Channels layer |
| `PRESENTATIONS_DIR` | Playwright temp output directory |
| `PRESENTATIONS_MAX_TABS` | Celery worker concurrency (default 10) |
| `PRESENTATIONS_GENERATION_TIMEOUT_MS` | Per-deck timeout (default 1 200 000 ms) |
| `STORAGE_BACKEND` | `auto` \| `s3` \| `sftp` \| `local` |

## Storage backend selection (`auto` mode)

`SFTP_HOST` set → **sftp**; else `S3_BUCKET` set → **s3**; else **local** (`storage/`).

S3 also requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION`.  
SFTP requires `SFTP_HOST`, `SFTP_USER`, and either `SFTP_PASSWORD` or `SFTP_PRIVATE_KEY_PATH`.

## Post-processing flags

| Variable | Default | Effect |
|---|---|---|
| `PRESENTATIONS_ZIP_OUTPUT` | `true` | Zip all output files |
| `PRESENTATIONS_ZIP_DELETE_ORIGINALS` | `true` | Remove originals after zipping |
| `PRESENTATIONS_PDF_GS_COMPRESS` | `true` | Compress PDF with GhostScript |
