# Manifests in the Dropbox photo flow

This project uses two JSON manifest files to safely connect Dropbox files,
local staged files, and ingest decisions.

## Why manifests exist

The Dropbox sync flow runs in phases:

1. Download Dropbox files into a local staging folder.
2. Run photo ingest on those local staged files.
3. Apply ingest outcomes back to Dropbox (remove accepted files, quarantine rejected files).

Manifests are the handoff between those phases.

## What `site-photo-inbox` is

`site-photo-inbox` is the Dropbox source folder. It is the inbox where uploads
arrive.

During sync, files are copied from `site-photo-inbox/...` into a temporary local
staging directory so ingest can process them as local files.

## Manifest 1: download manifest

Created by:

```bash
uv run python -m tooling.sync_dropbox_inbox download ... --manifest <path>
```

Purpose:

- Maps each original Dropbox path to the local staged file path.
- Records exactly what the download phase staged.

Dummy example:

```json
[
  {
    "source_path": "/site-photo-inbox/iphone/IMG_1001.HEIC",
    "staging_path": "/tmp/dropbox-stage/iphone/IMG_1001.HEIC"
  },
  {
    "source_path": "/site-photo-inbox/street/DSC_0204.JPG",
    "staging_path": "/tmp/dropbox-stage/street/DSC_0204.JPG"
  }
]
```

## Manifest 2: ingest results manifest

Created by:

```bash
uv run python -m tooling.ingest_photos ... --result-manifest <path>
```

Purpose:

- Records the ingest decision for each local staged file.
- Contains status (`ingested` or `skipped`) and optional skip reason.

Dummy example:

```json
[
  {
    "source_file": "/tmp/dropbox-stage/iphone/IMG_1001.HEIC",
    "status": "ingested"
  },
  {
    "source_file": "/tmp/dropbox-stage/street/DSC_0204.JPG",
    "status": "skipped",
    "reason": "missing-exif-datetimeoriginal"
  }
]
```

## How reconcile uses both manifests

Reconcile joins the manifests by local staged path:

- download manifest: `source_path` <-> `staging_path`
- ingest results: `source_file` == `staging_path`

That gives a safe Dropbox action per file:

- `ingested` -> remove from `/site-photo-inbox/...`
- `skipped` -> move to quarantine folder

## End-to-end dummy example

```text
Dropbox inbox file: /site-photo-inbox/iphone/IMG_1001.HEIC
       |
       | download phase
       v
Local staged file: /tmp/dropbox-stage/iphone/IMG_1001.HEIC
       |
       | ingest phase writes status=ingested
       v
reconcile phase deletes /site-photo-inbox/iphone/IMG_1001.HEIC
```

If status is `skipped`, reconcile moves the same Dropbox file to quarantine
instead of deleting it.
