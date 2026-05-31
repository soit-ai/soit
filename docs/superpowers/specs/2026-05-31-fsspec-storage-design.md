# Fsspec Storage Adapter Design

Date: 2026-05-31

## Goal

Replace SOIT-Pro's direct MinIO/boto3 storage path with a single fsspec-backed storage adapter, and add streaming storage capabilities so future backends and large-object flows can be adopted without changing business modules.

## Context

Affected area: backend (`server`)

Relevant current structure:

- `server/app/kernel/ports/storage/interface.py` defines the stable `StoragePort` interface.
- `server/app/kernel/ports/storage/policy.py` owns timeout, retry, tracing, and cost accounting.
- `server/app/adapters/storage/minio.py` currently connects to MinIO/S3 directly through boto3.
- `server/app/adapters/storage/memory.py` supports tests and lightweight flows.
- `server/app/wiring/container.py` creates the default storage adapter.
- Knowledge, audit, trace, and plugin/tool policy paths depend on `StoragePort`, not on a concrete MinIO client.

Architecture boundaries:

- `kernel/` owns port contracts and policy wrappers.
- `adapters/` owns concrete fsspec implementation details.
- `modules/` keep business logic and depend only on the storage port.
- `api/` remains an orchestration layer.

## Decision

Use an aggressive replacement:

- Add `FsspecStoragePort` as the production storage adapter.
- Stop using direct MinIO/boto3 as the default storage path.
- Treat MinIO as one possible S3-compatible endpoint behind fsspec, configured through `s3://` plus storage options.
- Keep the kernel `StoragePort` abstraction as the business-facing contract.
- Add streaming storage interfaces as part of the target architecture.

The old MinIO adapter may be removed during implementation or kept only as a non-default temporary fallback while tests are migrated. New runtime wiring must not instantiate direct MinIO/boto3 storage.

## Configuration

Introduce storage-neutral settings:

```env
STORAGE_URL=s3://soit-artifacts
STORAGE_OPTIONS_JSON={"endpoint_url":"http://minio:9000","key":"soitminio","secret":"soitminio"}
STORAGE_AUTO_MKDIR=true
```

Local development without MinIO:

```env
STORAGE_URL=file://./var/storage
STORAGE_OPTIONS_JSON={}
STORAGE_AUTO_MKDIR=true
```

Configuration rules:

- `STORAGE_URL` is required outside tests unless the environment deliberately uses in-memory storage.
- `STORAGE_OPTIONS_JSON` is parsed into a dictionary and passed to fsspec.
- `STORAGE_AUTO_MKDIR` controls parent directory creation for filesystems that need it.
- Existing `MINIO_*` settings are deprecated. If migration compatibility is needed, `MINIO_*` may be translated into `STORAGE_URL` and fsspec S3 options for one release, with a warning.
- New documentation and examples should use `STORAGE_*`, not `MINIO_*`.

Protocol examples:

- `file://./var/storage`
- `s3://soit-artifacts`
- `gs://soit-artifacts`
- `az://soit-artifacts`

Protocol-specific packages are explicit dependencies. The initial implementation needs `fsspec`; S3-compatible storage needs `s3fs`. Other protocols can be added later through their fsspec-compatible packages.

## Path Model

Business code continues to pass relative object keys:

- `tenants/{tenant_id}/workspaces/{workspace_id}/knowledge/...`
- `knowledge/{knowledge_id}/documents/...`
- `audit/{run_id}/{step_id}.json`
- `artifacts/...`

The adapter joins keys with `STORAGE_URL`:

- `s3://soit-artifacts/tenants/...`
- `file://./var/storage/tenants/...`

Key validation:

- Empty keys are rejected.
- Absolute local paths are rejected.
- Keys containing `..` path traversal segments are rejected.
- Backslashes are normalized to `/`.
- Leading slashes are stripped after validation.
- Business callers should not pass full protocol URLs. The configured storage root is the only mount point for the first version.

This keeps tenancy and workspace layout explicit in business-generated keys while keeping protocol and credential details inside the adapter.

## Adapter Behavior

`FsspecStoragePort` implements the existing `StoragePort` methods:

- `put(key, data, content_type=None, metadata=None, **kwargs) -> str`
- `get(key, **kwargs) -> bytes`
- `delete(key, **kwargs) -> None`
- `exists(key, **kwargs) -> bool`

Behavior rules:

- `put` opens the resolved fsspec path in binary write mode and writes the supplied bytes.
- `get` opens the resolved fsspec path in binary read mode and returns bytes.
- `delete` is idempotent; a missing object is a successful delete.
- `exists` checks the exact object path. Directory or prefix existence must not be treated as object existence.
- `content_type` and `metadata` are best-effort in the first version because support differs across fsspec backends.
- Business-critical metadata remains in the database, not in object metadata.
- Sync fsspec operations run through `asyncio.to_thread` when the backend API is synchronous, so FastAPI event loops are not blocked.
- Timeout, retry, trace, and cost recording remain in `StoragePolicyGateway`.

Error normalization:

- Invalid keys raise a deterministic storage error.
- Missing objects during `get` raise a deterministic not-found storage error.
- Backend errors are wrapped or allowed to be wrapped by `StoragePolicyGateway` into existing storage error codes.
- Protocol-specific exceptions must not leak into knowledge, trace, audit, or API handlers.

## Streaming Interface

The current storage interface uses whole-object `bytes`. That is useful but incomplete for large objects.

Current `bytes` interface advantages:

- Simple and easy to reason about.
- Matches existing knowledge upload, chunk artifact, parsed artifact, audit artifact, and trace artifact flows.
- Gives stable behavior across memory, local file, and S3-like storage.
- Keeps business code focused on object storage rather than filesystem details.
- Makes tests straightforward.

Current `bytes` interface disadvantages:

- Uploads and downloads load whole objects into memory.
- Large files create high memory pressure in API, parser, and storage layers.
- It cannot express streaming upload, streaming download, resumable write, or backpressure.
- fsspec can expose file-like objects, but the current `StoragePort` contract cannot use them.
- Some document parsers require full files or local paths, so a pure `bytes` path encourages repeated buffering.

Add streaming as an extension, not as a breaking replacement:

```python
class StorageReader(Protocol):
    async def read(self, size: int = -1) -> bytes: ...
    async def close(self) -> None: ...


class StorageWriter(Protocol):
    async def write(self, data: bytes) -> int: ...
    async def close(self) -> None: ...


class StreamingStoragePort(StoragePort):
    async def open_reader(self, key: str, **kwargs: Any) -> StorageReader: ...

    async def open_writer(
        self,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> StorageWriter: ...
```

Reader and writer objects must support async context manager usage:

```python
async with storage.open_writer(key) as writer:
    await writer.write(chunk)
```

Streaming behavior:

- `FsspecStoragePort` implements both `StoragePort` and `StreamingStoragePort`.
- `put` and `get` may internally use `open_writer` and `open_reader` for consistency.
- Writer close failure means the write failed.
- Size and checksum can be calculated while streaming data into storage.
- Streaming does not change key format, tenancy layout, or policy gateway behavior.

## Phased Implementation Plan

### Phase 1: Fsspec Replacement

Deliverables:

- Add fsspec settings to `server/app/settings/settings.py`.
- Add `server/app/adapters/storage/fsspec.py`.
- Update `server/app/wiring/container.py` to create `FsspecStoragePort` outside tests.
- Replace default direct MinIO/boto3 wiring.
- Update `.env.example` and docker compose backend environment to use `STORAGE_*`.
- Add `fsspec` and `s3fs` dependencies.
- Keep `InMemoryStoragePort` for tests.

Acceptance:

- Existing storage consumers continue using `StoragePort`.
- Knowledge upload, parsed text artifact, chunk artifact, audit artifact, and trace artifact flows still work through the port.
- No production wiring instantiates `MinIOStoragePort`.

### Phase 2: Streaming Port

Deliverables:

- Add streaming protocols or abstract interfaces under `server/app/kernel/ports/storage/`.
- Implement fsspec-backed async reader and writer wrappers.
- Add tests for streaming write/read roundtrip on `file://`.
- Ensure reader and writer close resources correctly on success and failure.

Acceptance:

- `FsspecStoragePort` passes both whole-object and streaming tests.
- `put/get` remain compatible.
- Large-object API can use streaming without changing adapter internals.

### Phase 3: Business Flow Streaming

Deliverables:

- Change knowledge raw upload persistence to stream into storage where the upload source supports chunked reads.
- Compute `size_bytes`, `checksum`, and `content_hash` during streaming write.
- Keep small-file `bytes` fast paths where they simplify existing code.
- Add parser-side support for temporary files or file-like inputs for formats that cannot parse directly from streams.
- Use streaming for future large download/export endpoints.

Acceptance:

- Raw upload memory usage no longer scales directly with uploaded file size when streaming input is available.
- DB metadata remains consistent with stored object content.
- Existing document ingestion behavior is preserved.

## Testing Strategy

Unit tests:

- `file://` put/get roundtrip.
- `file://` streaming write/read roundtrip.
- nested key parent creation.
- delete idempotency.
- exact object `exists` true/false.
- invalid key rejection for empty keys, absolute paths, and traversal.
- `put/get` compatibility after streaming implementation.

Integration tests:

- Optional MinIO/S3-compatible test behind `SOIT_STORAGE_INTEGRATION=1`.
- Validate `s3://bucket` plus `endpoint_url`, `key`, and `secret`.
- Validate object write/read/delete through fsspec, not direct boto3 client usage in SOIT code.

Regression tests:

- Knowledge runtime tests continue passing with in-memory or file-backed storage.
- Trace/audit artifact storage behavior remains unchanged from caller perspective.

## Risks And Mitigations

Risk: fsspec protocol behavior differs across backends.

Mitigation: Keep `StoragePort` semantics narrow and object-oriented. Treat metadata as best-effort. Add protocol-specific integration tests only where a backend is officially supported.

Risk: S3-compatible stores do not behave like POSIX filesystems.

Mitigation: Do not expose directory semantics. Keys are object paths. `exists` checks exact object paths only.

Risk: Streaming expands the scope of the change.

Mitigation: Implement fsspec replacement first, then add streaming interfaces, then migrate business flows. The design includes streaming, but implementation remains phased.

Risk: Parser libraries may still require full files.

Mitigation: Use temporary files for parser paths that need seekable local files. Avoid forcing pure streaming where third-party parsers do not support it.

Risk: Existing `MINIO_*` deployment config breaks.

Mitigation: Provide a migration path from `MINIO_*` to `STORAGE_*` for one release or document the required environment change clearly before deployment.

## Rollback

Rollback is straightforward if the old MinIO adapter is temporarily retained:

- Set wiring back to `MinIOStoragePort`.
- Restore `MINIO_*` runtime settings.
- Keep `StoragePort` consumers unchanged.

If the old adapter is deleted, rollback requires reverting the fsspec replacement commit. Because the business-facing port remains unchanged, rollback should be isolated to adapter, settings, dependencies, and environment configuration.

## Documentation Updates

Update:

- `server/app/kernel/ports/storage/README.md`
- `server/docs/architecture/PROJECT_STRUCTURE.md` if storage adapter guidance changes.
- `.env.example`
- `docker/docker-compose.yml`

Docs should state:

- Storage is fsspec-backed.
- MinIO is configured as an S3-compatible fsspec endpoint.
- New storage protocols are added by installing fsspec-compatible dependencies and setting `STORAGE_URL` plus `STORAGE_OPTIONS_JSON`.
- `put/get` are for small objects; streaming interfaces are for large objects.

## Acceptance Checklist

- Storage adapter defaults to fsspec outside tests.
- Direct MinIO/boto3 storage path is no longer used by default.
- Existing whole-object storage behavior remains compatible.
- Streaming reader and writer are part of the target storage contract.
- Knowledge raw upload has a clear path to streaming without breaking current consumers.
- Tests cover file-backed fsspec behavior and optional S3-compatible integration.
- Documentation explains migration from `MINIO_*` to `STORAGE_*`.
