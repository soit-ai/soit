# kernel/ports/storage/

Gateway interface + shared logic for `storage`.

Rules:
- Implement policy enforcement here (where applicable).
- Concrete implementations belong to `adapters/`.

Runtime storage is backed by fsspec. Business code passes relative object keys
through `StoragePort`; adapters resolve those keys under `STORAGE_URL`.

Configuration:

```env
STORAGE_URL=s3://soit-artifacts
STORAGE_OPTIONS_JSON={"endpoint_url":"http://object-storage:9000","key":"access-key","secret":"secret-key"}
STORAGE_AUTO_MKDIR=true
```

Object storage endpoints are configured through `STORAGE_URL` and
`STORAGE_OPTIONS_JSON`. Other protocols require their fsspec package, such as
`gcsfs` for `gs://` or `adlfs` for Azure storage.

Use `put` and `get` for small objects. Use `StreamingStoragePort.open_reader`
and `StreamingStoragePort.open_writer` for large objects and flows where memory
usage should not scale with object size.
