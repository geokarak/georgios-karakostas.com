# Dropbox sync state

The Dropbox workflow passes one JSON file through download, ingest, and finalize.
The file is temporary workflow state, not site content.

Each entry contains:

- `source_path`: original absolute Dropbox path
- `source_file`: absolute local staging path, or an empty string when the path
  cannot be safely staged
- `status`: omitted after a successful download until ingest completes; then
  `ingested` or `skipped`
- `reason`: optional explanation for a skipped entry

Example after download:

```json
[
  {
    "source_path": "/site-photo-inbox/iphone/photo.jpg",
    "source_file": "/tmp/dropbox-inbox/iphone/photo.jpg"
  }
]
```

Ingest adds `status: "ingested"` after writing the photo, or
`status: "skipped"` when the file cannot be imported. Files rejected before
download are recorded as skipped with a reason such as `invalid-dropbox-path`
or `file-too-large`.

Finalize removes ingested files from the Dropbox inbox and moves skipped files
to quarantine. Missing or unsupported statuses stop finalization rather than
guessing. The schema and validation rules are implemented in
`tooling/dropbox_sync/state.py` and `tooling/dropbox_sync/finalize.py`.
