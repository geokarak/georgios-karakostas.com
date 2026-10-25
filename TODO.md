# TODO

## Investigate PhotoSwipe migration

- [ ] Benchmark GLightbox vs PhotoSwipe on mobile (open speed, swipe smoothness, memory use) with real landscape and portrait photos.
- [ ] Compare feature set needed for this site: captions, keyboard/touch navigation, zoom behavior, loop behavior, and accessibility.
- [ ] Validate image centering and viewport behavior on iOS Safari and Android Chrome for landscape photos.
- [ ] Check bundle/loading impact of PhotoSwipe integration against the current self-hosted GLightbox assets.
- [ ] Evaluate maintenance complexity in Pelican templates (initial integration + future changes).
- [ ] If benefits are clear, create a migration plan and rollback path from GLightbox.

## Harden Dropbox photo sync workflow

- [ ] Confirm who has write access to the configured Dropbox inbox path and whether that access is intentionally equivalent to site publication authority.
- [ ] Confirm whether GitHub branch protection/rulesets allow this workflow's `GITHUB_TOKEN` to push to `main` without the usual review/check gates.
- [ ] Confirm whether any lower-trust principal can control article/page metadata or photo sidecar metadata that reaches rendered templates in production.

## Template URL helpers

- [ ] Add a shared Jinja macro for internal links so templates stop building root-relative and `SITEURL`-aware URLs ad hoc.

## Performance optimizations

- [ ] Chunk batched EXIF extraction in `tooling/ingest_photos.py` if very large imports ever make the current in-memory batch lookup too heavy.
- [ ] Refactor derivative generation in `tooling/ingest_photos.py` to decode/normalize each source image once, then write display + thumbnail variants from that single pass.
- [ ] Add `loading="lazy"` and `decoding="async"` on gallery thumbnails in `theme/templates/gallery.html`.
- [ ] Cache already-created remote quarantine folders in `tooling/dropbox_sync/api.py` to avoid repeated Dropbox folder-create API calls.
