# Dropbox sync state file

This project uses one JSON state file to safely connect Dropbox files, local
staged files, and ingest decisions.

## Why the state file exists

The Dropbox sync flow runs in phases:

1. Download Dropbox files into a local staging folder.
2. Run photo ingest on those local staged files.
3. Finalize ingest outcomes back in Dropbox.

The state file is the handoff across those phases.

## What `site-photo-inbox` is

`site-photo-inbox` is the Dropbox source folder. It is the inbox where uploads
arrive.

During sync, files are copied from `site-photo-inbox/...` into a temporary
local staging directory so ingest can process them as local files.

## State file structure

Created initially by:

```bash
uv run python -m tooling.sync_dropbox_inbox download ... --state-file <path>
```

Updated later by:

```bash
uv run python -m tooling.ingest_photos ... --result-manifest <same-path>
```

Read finally by:

```bash
uv run python -m tooling.sync_dropbox_inbox finalize ... --state-file <same-path>
```

Example:

```json
[
  {
    "source_path": "/site-photo-inbox/iphone/IMG_1001.JPG",
    "source_file": "/tmp/dropbox-stage/iphone/IMG_1001.JPG",
    "status": "ingested"
  },
  {
    "source_path": "/site-photo-inbox/street/DSC_0204.JPG",
    "source_file": "/tmp/dropbox-stage/street/DSC_0204.JPG",
    "status": "skipped",
    "reason": "missing-exif-datetimeoriginal"
  }
]
```

## Status values

- status omitted: download finished but ingest has not yet written a final outcome
- `ingested`: ingest accepted the file, so finalize removes it from Dropbox inbox
- `skipped`: ingest rejected the file, so finalize moves it to quarantine

## Finalize Behavior

Finalize reads the same state file and applies one Dropbox action per entry:

- `ingested` -> remove from `/site-photo-inbox/...`
- `skipped` -> move to the quarantine folder
- missing `status` -> stop instead of guessing
