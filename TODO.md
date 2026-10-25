# TODO

## Harden Dropbox photo sync workflow

- [ ] Confirm who has write access to the configured Dropbox inbox path and whether that access is intentionally equivalent to site publication authority.

## Template URL helpers

- [ ] Add a shared Jinja macro for internal links so templates stop building root-relative and `SITEURL`-aware URLs ad hoc.

## Performance optimizations

- [ ] Chunk batched EXIF extraction in `tooling/ingest_photos.py` if very large imports ever make the current in-memory batch lookup too heavy.
- [ ] Refactor derivative generation in `tooling/ingest_photos.py` to decode/normalize each source image once, then write display + thumbnail variants from that single pass.
- [ ] Cache already-created remote quarantine folders in `tooling/dropbox_sync/api.py` to avoid repeated Dropbox folder-create API calls.
