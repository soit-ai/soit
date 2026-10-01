# Knowledge connectors

A knowledge base normally holds what people upload. A **source** keeps it in
step with a system that already holds the documents: an S3-compatible bucket
or a website. A sync lists what the remote has, ingests what is new, saves what
changed as a new version, leaves what did not change alone, and, if you ask it
to, deletes the documents of items that went away.

This page covers the concepts, both connectors, scheduling, change detection,
limits and what is not included. The API is under
`/api/v1/knowledge/{knowledge_id}/sources`; the console has a **Sources** tab on
every knowledge base.

## Concepts

| Term | Meaning |
| --- | --- |
| Connector | A kind of remote system (`s3`, `web`) and the settings it takes. `GET /api/v1/knowledge/connectors` lists them with their fields. |
| Source | One configured connection feeding one knowledge base: connector settings, an optional secret, a schedule, limits and the `delete_removed` choice. A knowledge base can have up to 20. |
| Sync run | One execution of a source, manual or scheduled. Runs are queued, run by the sync worker and keep their counts and per-item outcomes. A source has at most one queued or running run at a time. |
| Item | One remote document (an object key, a page URL). SOIT remembers, per item, what it saw last time so the next sync can tell what changed. |

Documents a source creates have `source_kind = connector`, carry the remote
identity in `external_id` and `source_uri`, and keep a stable document key per
item, so a changed item becomes a new **version** of the same document and
rollback works as for any other document. They are ingested through the same
queue as uploads: parsing, chunking, embedding and their retries are the
ingest worker's, and a failure there shows up on the document and in the ingest
dead letters as usual. A knowledge base needs an index before it can sync, as
it does for uploads.

## Setting up a source

1. Create the secret the connector needs (S3 only) under Govern › Secrets.
2. In the knowledge base, open **Sources › Add source**, pick the connector,
   fill in its settings and **Test connection**. The test lists a sample of what
   would sync and ingests nothing.
3. Save, then **Sync now**, or set a schedule.

Through the API:

```bash
curl -X POST "$SOIT/api/v1/knowledge/$KB/sources" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "handbook bucket",
    "connector_kind": "s3",
    "config": {"bucket": "handbook", "region": "eu-west-1", "prefix": "docs/",
               "include": ["*.pdf", "*.md"]},
    "secret_id": "sec_...",
    "schedule_cron": "0 2 * * *",
    "schedule_timezone": "Europe/Berlin",
    "delete_removed": false
  }'
curl -X POST "$SOIT/api/v1/knowledge/$KB/sources/$SOURCE/sync" -H "Authorization: Bearer $TOKEN"
```

A sync answers `202` with the queued run; a second request while one is queued
or running answers `409`. `GET .../runs` is the history and `GET .../runs/{id}`
adds the per-item outcomes (everything except unchanged, the first 200).
`POST .../runs/{id}/cancel` cancels a queued run at once and asks a running one
to stop between items.

## S3-compatible storage (`s3`)

Works with AWS S3, MinIO, Cloudflare R2 and other services that speak the S3
API. SOIT lists the bucket with ListObjectsV2 and downloads objects with
GetObject, signing each request with Signature Version 4.

| Setting | Meaning |
| --- | --- |
| `bucket` (required) | The bucket name. |
| `region` | The bucket's region; default `us-east-1`. Many S3-compatible services accept any value. |
| `endpoint` | Leave empty for AWS. Set it for MinIO, R2 and others, for example `https://minio.example.com:9000`. No path, no credentials. |
| `prefix` | Only keys starting with this are synced. |
| `include` / `exclude` | Glob patterns matched against the whole key; `*` also matches `/`. A key must match an include pattern (when there are any) and no exclude pattern. |
| `path_style` | `endpoint/bucket/key` instead of `bucket.endpoint/key`. Defaults to on when an endpoint is set, and is always on for bucket names containing a dot. |

**Credentials** come from a secret whose value is JSON:

```json
{"access_key_id": "AKIA...", "secret_access_key": "...", "session_token": "..."}
```

`session_token` is optional. The source stores only the secret's id; the value
is read when a test or sync runs, used to sign requests and never written to
the source, a run, an audit event or a response. Credentials placed in the
source's configuration are refused.

Folder placeholder keys (ending in `/`) and files the knowledge parsers cannot
read are skipped and counted as skipped. Supported extensions: `.txt`, `.md`,
`.markdown`, `.html`, `.htm`, `.pdf`, `.docx`, `.pptx`, `.rst`, `.csv`, `.tsv`,
`.json`, `.yaml`, `.yml`, `.log`. A listing never gives up quietly: more than
500,000 objects under the prefix fails the run with a message to narrow the
prefix or patterns.

## Website crawl (`web`)

Starts at the seed URLs and follows links breadth-first.

| Setting | Meaning |
| --- | --- |
| `seed_urls` (required) | Up to 20 start URLs. |
| `max_depth` | Links to follow from a seed; default 2, at most 5. 0 reads only the seeds. |
| `max_pages` | Pages visited per sync; default 50, at most 500. |
| `path_prefix` | Only follow links whose path starts with this; seeds are always read. |

Rules the crawl always follows:

- Links are followed only on the seeds' own hosts (and ports). A redirect to
  another host is not followed.
- `robots.txt` is fetched once per host and obeyed, including `*` and `$`
  patterns and `Crawl-delay` (up to 5 seconds). A missing file allows everything;
  one that cannot be read because the server errors disallows everything. The
  crawler identifies itself as `SOITKnowledgeBot`.
- `noindex` and `nofollow` robots meta tags and `rel="nofollow"` links are
  honoured.
- No credentials, cookies or custom headers are sent: only public pages can be
  read. A secret on a web source is refused.
- HTML, plain text, Markdown and PDF are accepted, up to 5 MB per page. URLs
  are normalized (host case, fragment, default port) so a page is read once.
- Pages the previous sync saw are requested with `If-None-Match` and
  `If-Modified-Since`; a `304` costs no download and the stored links are
  followed, so the rest of the site is still reached.

A page that fails for a transient reason (a 5xx, a timeout) is reported as
failed, never as removed. A page that is gone (404 or 410) or no longer linked
within the depth and page limits is "removed" for the purposes of
`delete_removed`. A crawl cut off by `max_pages` is incomplete, so nothing is
removed on that run. A failing seed (not found, blocked by robots.txt, server
error) fails the run rather than deleting everything the crawl used to find.

## Change detection

For each item the sync decides in this order:

1. **Unchanged by the remote's own markers**: the ETag (or, if the remote has
   none, the modification marker) equals what was recorded, the size agrees, and
   the item's document still exists. Nothing is downloaded.
2. **Unchanged by content**: the markers differ but the downloaded bytes hash
   (SHA-256) to what was ingested last time. The new markers are remembered, no
   new version is made.
3. **Changed**: a new version of the same document is created and queued for
   ingest (`updated`).
4. **New**: a new document is created (`added`).
5. **Gone from the remote**: see below (`removed`).
6. **Could not be synced** (download refused, too large, empty): the item is
   `failed` with its error, the rest of the run carries on and the run ends
   `partial`. The item is retried by the next run.

If someone deletes a synced document by hand, the next sync creates it again as
long as the item still exists remotely: the remote is the source of truth.
Manual edits to a synced document's chunks are overwritten by the next
version; document-level edits are not tracked.

## Removed items

When an item disappears from a complete listing:

- with `delete_removed` **off** (the default) the document is kept and the item
  is marked removed. If the item returns unchanged, it is picked up again
  without a download;
- with `delete_removed` **on** every version of its document is deleted, like
  deleting the document in the console.

Removal is decided only from a listing that finished. A run that failed part
way, was canceled, hit one of its caps or reported itself incomplete (a crawl
that reached `max_pages`) never removes anything.

## Scheduling

A source takes a five-field cron expression and a time zone
(`schedule_cron`, `schedule_timezone`), for example `0 2 * * *` in
`Europe/Berlin`. Without one it syncs only on demand. Syncs of one source may
not be closer than `KNOWLEDGE_SYNC_MIN_INTERVAL_SECONDS` (default 300). A
disabled source is neither scheduled nor synced on demand.

The sync worker checks for due sources every
`KNOWLEDGE_SYNC_SCHEDULER_INTERVAL_SECONDS` (default 30), queues a run for each
and computes the next firing. If the previous run of a source is still going when
its schedule fires again, that firing is skipped rather than stacked.

The worker runs wherever the ingest worker runs, because a sync hands its
documents to it: in the API process when `KNOWLEDGE_INGEST_WORKER_ENABLED` is
on, in `scripts/ingest_worker.py` and in `scripts/combined_worker.py`.
`KNOWLEDGE_SYNC_WORKER_ENABLED=false` turns the sync half off. It uses leases
like the other workers: a run whose worker died is reclaimed once its lease
expires and starts over, which is safe because items already synced compare as
unchanged; a run interrupted `KNOWLEDGE_SYNC_MAX_ATTEMPTS` times (default 3) is
given up on.

## Limits

Every sync is bounded. Each source may set its own caps, within the
deployment's ceilings:

| Cap | Default | Ceiling setting |
| --- | --- | --- |
| Items per run | 1,000 | `KNOWLEDGE_SYNC_MAX_ITEMS_CEILING` (20,000) |
| Bytes per item | 5 MB | `KNOWLEDGE_SYNC_MAX_ITEM_BYTES_CEILING` (50 MB) |
| Bytes downloaded per run | 256 MB | `KNOWLEDGE_SYNC_MAX_TOTAL_BYTES_CEILING` (4 GB) |

The defaults are `KNOWLEDGE_SYNC_DEFAULT_MAX_ITEMS`,
`KNOWLEDGE_SYNC_DEFAULT_MAX_ITEM_BYTES` and
`KNOWLEDGE_SYNC_DEFAULT_MAX_TOTAL_BYTES`. An item over the per-item cap fails
without being downloaded when its size is known. Reaching the item or total cap
ends the run early and marks it truncated (`truncated` on the run, "cut off" in
the console); nothing is removed on a truncated run. The web crawl's own caps
are `max_depth` and `max_pages` above.

## Network access and private endpoints

Connectors reach the network only through SOIT's governed egress, the same
policy that guards tool calls and web fetches: every request and every redirect
hop is checked against the tenant and workspace allow and block lists, and an
address that resolves to a private or loopback network is refused unless its
network is listed in `EGRESS_PRIVATE_NETWORKS`.

So for a MinIO on an internal network, or a documentation site on an intranet,
both steps are needed: allow the host in the workspace egress policy, and add
its network (for example `10.0.0.0/8`) to `EGRESS_PRIVATE_NETWORKS`. A refusal is
reported on **Test connection** and on the run with the host and the setting to
change, rather than as a generic failure.

## Failures and dead letters

- A failing item makes the run `partial` and is listed in the run's outcomes.
- A listing or credential failure (rejected credentials, unreachable endpoint,
  egress refusal, a crawl seed that is gone) fails the run. The source shows the
  error and the run's status.
- A failed run appears in Observe's dead letters as `knowledge_sync` until a
  later run of the same source exists. Redrive queues a fresh run of the source;
  the failed run stays as the record.

Audit events are written for creating, changing and deleting a source
(`knowledge.source.created`, `.updated`, `.deleted`) and for each sync
(`knowledge.source.sync.started`, `.finished`). They hold counts, ids and names,
never credentials.

## Access control

Reading sources and runs needs read access to the knowledge base; creating,
changing, testing, syncing, cancelling and deleting needs update access, with
the knowledge base's visibility applied: a private knowledge base's sources are
as hidden as the base itself. Sources are scoped to the tenant and workspace.

Documents a connector creates take the knowledge base's own visibility. **Mapping
the access rights of the source system (who may read an object or page) onto
documents is not part of this version**: everyone who can retrieve from the
knowledge base can retrieve from synced documents. Do not sync content into a
knowledge base that is shared more widely than the content is. Enforcing
document-level access is a separate piece of work.

## What is not included

- Mapping source permissions to document access (see above).
- OAuth and SaaS connectors (Google Drive, Notion, Confluence, ...). The
  connector contract (`app/kernel/ports/connectors`) is small, and each new kind
  is a module under `app/adapters/connectors` registered in
  `app/wiring/connectors.py`.
- Authenticated or JavaScript-rendered websites.
- Detecting or preserving manual changes to a synced document. A changed item
  becomes a new version, and a deleted document is recreated.
- Deleting a source's documents when the source is deleted: the documents stay
  in the knowledge base and are simply no longer kept in step.
