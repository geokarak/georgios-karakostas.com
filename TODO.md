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
