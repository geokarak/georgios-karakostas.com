# TODO

## Investigate PhotoSwipe migration

- [ ] Benchmark GLightbox vs PhotoSwipe on mobile (open speed, swipe smoothness, memory use) with real landscape and portrait photos.
- [ ] Compare feature set needed for this site: captions, keyboard/touch navigation, zoom behavior, loop behavior, and accessibility.
- [ ] Validate image centering and viewport behavior on iOS Safari and Android Chrome for landscape photos.
- [ ] Check bundle/loading impact of PhotoSwipe integration (CDN vs self-hosted assets).
- [ ] Evaluate maintenance complexity in Pelican templates (initial integration + future changes).
- [ ] If benefits are clear, create a migration plan and rollback path from GLightbox.

## Harden Dropbox photo sync workflow

- [ ] Handle races between normal pushes and the scheduled Dropbox photo sync workflow, likely by rebasing on the latest `main` before the automation commits and pushes.

## Template URL helpers

- [ ] Add a shared Jinja macro for internal links so templates stop building root-relative and `SITEURL`-aware URLs ad hoc.

## Performance optimizations

- [ ] Chunk batched EXIF extraction in `scripts/ingest_photos.py` if very large imports ever make the current in-memory batch lookup too heavy.
- [ ] Refactor derivative generation in `scripts/ingest_photos.py` to decode/normalize each source image once, then write display + thumbnail variants from that single pass.
- [ ] Add `loading="lazy"` and `decoding="async"` on gallery thumbnails in `theme/templates/gallery.html`.
- [ ] Stream Dropbox file downloads in `scripts/sync_dropbox_inbox.py` (chunked write) instead of reading full responses into memory.
- [ ] Cache already-created remote archive folders in `scripts/sync_dropbox_inbox.py` to avoid repeated Dropbox folder-create API calls.
