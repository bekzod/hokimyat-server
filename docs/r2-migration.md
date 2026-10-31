# Private EU R2 migration (draft)

Code preparation only: no buckets, credentials, documents, audio files, or deployed
configuration are changed. `STORAGE_PROVIDER=minio` preserves current behavior.
Both Python services keep their pinned boto3 1.34.30 client and thread-offloaded
I/O; moving these services to Bun would be unrelated to the storage migration.

## Services and private buckets

| Service | Existing bucket setting | EU R2 destination setting |
| --- | --- | --- |
| OCR API + Celery worker | `MINIO_UPLOADS_BUCKET` | `R2_BUCKET` |
| Meeting audio service | `AUDIO_BUCKET` | `R2_AUDIO_BUCKET` |

Both destinations must remain private: disable r2.dev and public custom-domain
access. Prefer separate EU-jurisdiction document and audio buckets for access and
retention boundaries. The existing object keys, metadata/MIME types, listing and
presigned-download behavior are unchanged. Object URLs are never made public.

Use separate `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` credentials scoped to the
intended private buckets and the required read/write/list operations. Set
`R2_ENDPOINT=https://<32-character-account-id>.eu.r2.cloudflarestorage.com`.
Only the EU jurisdiction endpoint is accepted; `auto` is the signing region,
not a location choice. TLS verification is mandatory in R2 mode. Missing R2
settings never reuse MinIO credentials. R2 mode does not check/create buckets
at client construction; provision destinations only through separately approved
operator action. Existing MinIO provisioning remains local and unchanged.

The services have independent Docker build contexts, so their small
`storage_config.py` modules are intentionally self-contained. Compose already
passes root `.env` to both. Keep `MINIO_*`, local MinIO/init services and volumes
for rollback; **never repoint MINIO_ENDPOINT to R2**, because init-minio creates
local buckets. Set the new R2 variables instead. Restart every service after
configuration changes because settings and clients are cached.

## Approval gates, cutover and rollback

1. Obtain explicit approval for moving legal documents/meeting audio to an
   external provider, including EU jurisdiction, retention and access controls.
   No data transfer is included in this PR.
2. Inventory both source buckets. Separately provision private **EU-jurisdiction**
   R2 buckets, scoped credentials and any required retention policy; then copy
   exact keys, bytes, MIME types and metadata under an approved operation.
   Compare counts/sizes and sample byte hashes; multipart ETags are not hashes.
3. Switch `STORAGE_PROVIDER=r2` in staging only, with all new variables filled.
   Verify OCR byte/stream uploads, Unicode metadata, listing, size/404/permission
   behavior, authenticated downloads, deletes and full Docling processing. Verify
   audio upload/list and expiring presigned playback links from the browser.
   Configure CORS only for intended playback origins if necessary; CORS is not
   public access. Check that unsigned requests cannot retrieve sensitive objects.
4. Separately approve production cutover. Pause uploads/recordings and drain
   workers, make/verify a final delta copy, restart API/workers/audio together,
   smoke test, then resume. Avoid unsynchronized mixed-provider writers.
5. Rollback before new writes: restore `STORAGE_PROVIDER=minio` and restart.
   After R2-only writes: first pause/drain, reconcile and separately copy new
   objects back to the corresponding MinIO buckets preserving metadata; then
   switch. Keep both systems and old signed URLs available until expirations
   and reconciliation are complete. Do not delete data or revoke credentials
   during the rollback window.

## Offline tests

With the existing service dependencies installed:

```bash
(cd ocr && python -m unittest discover -s tests -p test_storage_r2.py -v)
(cd audio && python -m unittest discover -s tests -p test_storage_r2.py -v)
```

These use real offline boto3 signing and mocked network transports; no buckets
or objects are created. Full deployed integration and live EU R2/CORS tests are
still required before rollout.

References: [Cloudflare boto3](https://developers.cloudflare.com/r2/examples/aws/boto3/),
[EU endpoints](https://developers.cloudflare.com/r2/api/tokens/),
[S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/).
