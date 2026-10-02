# Knowledge access

Who may read a knowledge base, and which of its documents.

## Knowledge bases

A knowledge base's `visibility` decides who reaches it at all:

| Visibility | Readers |
| --- | --- |
| `private` | its creator and the workspace's Owners and Admins, plus holders of a `knowledge` grant |
| `workspace` (default) | every member of the workspace, by role: Viewers read, Developers also query and upload |
| `tenant` | also members of the tenant's other workspaces, to read and query (an Owner or Admin shares it) |

Only the creator or a workspace Owner or Admin changes it.

## Restricted documents

A document can be kept from readers of its knowledge base. A restricted
document is readable only by:

- the workspace's Owners and Admins,
- the knowledge base's creator,
- members and service principals holding a `knowledge_document` grant with
  the `read` action on it.

Everyone else meets it nowhere. It is left out of the document listing; the
document, its content, its download, its chunks and its versions answer
`404`; and retrieval leaves it out before ranking, reranking or the keyword
fallback see it, for every strategy (vector, keyword, hybrid, multi-index).
An agent's RAG, a workflow's retrieve node, the `knowledge_query` tool and
MCP all retrieve through the same query, as the caller. The retrieval step of
a run records how many restricted documents it left out
(`restricted_documents_excluded` in its metrics).

A restriction names the document by its key (`doc_key`), so it holds for
every version: a new upload, a connector sync bringing a new version, and a
rollback to an old one all stay restricted. It takes effect, and lifts, at
once; no cache stands between a change and the next read.

```
GET /api/v1/knowledge/{id}/document-restrictions
PUT /api/v1/knowledge/{id}/document-restrictions   {"doc_key": "payroll", "restricted": true}
```

- Only a workspace Owner or Admin or the knowledge base's creator restricts
  a document or lifts a restriction. Each change is written to the audit
  ledger as `knowledge.document.restricted` or `knowledge.document.unrestricted`.
- The listing answers the restricted documents the caller may read; a reader
  is not told which documents are kept from them.
- To open a restricted document to one member, a workspace Owner or Admin
  grants it with `POST /api/v1/resource-grants`:
  `{"resource_type": "knowledge_document", "resource_id": "<knowledge id>:<doc_key>", "user_id": "...", "actions": ["read"]}`.
  Each restriction in the listing carries that `grant_resource_id`.

In the console, **Access** on a document's row in **Build › Knowledge** shows
whether it is restricted, restricts it or lifts the restriction, and, once it
is restricted, lists the members granted read and grants or revokes it.

## Connector-synced documents

Documents a [connector](knowledge-connectors.md) syncs take the knowledge
base's visibility, and can be restricted one by one like any other; the
restriction survives every later sync of the same item. SOIT does not map the
source system's own permissions onto documents: keep content with different
audiences in different knowledge bases, or restrict the documents that need it.

## Copies kept in runs, responses and threads

Runs keep what retrieval returned: citations, `knowledge_query` results, a
source event, a thread message's citations and tool results. Reading them
back obeys the reader's access now, not the access of whoever ran the
retrieval or the access when it ran. A document the reader may not read
(restricted from them, or in a private knowledge base of someone else's, or
in a base not shared with their workspace) is left out of every list it
appears in, totals are recounted, and a single item outside a list is
replaced by a withheld marker. This applies to run detail (citations, tool
calls and response events), the response endpoints and their event stream,
thread messages, tool result downloads, and a repeated tool call answered
from its stored result. The stored records themselves are not changed, so
lifting a restriction shows them again.

A copy that names a document no longer present, a deleted document or
knowledge base, is shown as it was: there is nothing left to enforce.

## Not covered yet

- Text kept as a whole: a step's output summary, a workflow's retrieve node
  output, an agent's retrieved context in an approval checkpoint, and answers
  a model wrote from retrieved text. These are not filtered item by item.
- Groups: a grant names one member or service principal.
