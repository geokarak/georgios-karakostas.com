# georgios-karakostas.com

Source for [georgios-karakostas.com](https://www.georgios-karakostas.com).

Made with [Pelican](https://github.com/getpelican/pelican). Deployed using [Cloudflare Pages](https://pages.cloudflare.com/).

## Photo workflow

Drop new photos into `inbox/<category>/` and run:

```bash
make ingest
```

`make ingest` uses `INGEST_SRC=inbox` unless another source is passed explicitly. It reads the uploaded images from category subfolders, writes the published files into `content/images/photos/...`, and removes the source files from the inbox so the same photos are not imported again on the next run. The ingest step stages files before committing them, so a failure does not leave half-written outputs behind or delete the original photo too early. The project requires `exiftool`, and photos without `EXIF:DateTimeOriginal` are skipped.

Each ingested photo creates:

- `content/images/photos/<category>/<id>-display.webp`
- `content/images/photos/<category>/<id>-thumb.webp`
- `content/images/photos/<category>/<id>.json`

The JSON file is generated automatically with the photo id, category, `DateTimeOriginal`, and derivative filenames. It can be edited later for `caption`, `location`, and `published`.

Only web-ready derivatives are stored in the repository: a display image and a thumbnail, both as WebP.

Any new category folder under `inbox/` (for example `inbox/macro/`) is automatically available as a browsable gallery page at `/<category>/` after ingest + build.

## How photo pages work

The photo pipeline has two main steps:

1. `tooling/ingest_photos.py` reads uploaded images from `inbox/<category>/` and writes web-ready files into `content/images/photos/<category>/`.
2. `plugins/photos/photos.py` reads those generated files and passes the photo data to the templates that render the gallery pages.

For a step-by-step explanation of the ingest script flow, see `docs/INGEST_PHOTOS_FLOW.md`.

The plugin reads the photo location from Pelican settings via `PHOTOS_PATH`, which currently points to `content/images/photos/`.

For each published photo, `content/images/photos/<category>/` contains:

- `<id>.json`
- `<id>-display.webp`
- `<id>-thumb.webp`

The JSON file stores the photo metadata and points to the display and thumbnail image filenames.

The main template files involved are:

- `theme/templates/gallery.html` for one gallery page such as `/iphone/`
- `theme/templates/photography_index.html` for the page that links to the available galleries

Useful options:

```bash
# Use the default local inbox.
# `--src` points to the folder that contains category subfolders.
uv run python -m tooling.ingest_photos --src inbox

# Preview what would be created without writing files.
# `--dry-run` prints the planned output paths only.
uv run python -m tooling.ingest_photos --src inbox --dry-run
```

## Dropbox uploads

The local `inbox/` workflow can stay in place alongside a Dropbox-based upload path.

Dropbox sync state is documented in `docs/DROPBOX_SYNC_STATE.md`.

For a step-by-step explanation of Dropbox orchestration script flow, see `docs/SYNC_DROPBOX_INBOX_FLOW.md`.

The `.github/workflows/dropbox-photo-sync.yml` workflow runs twice per day and can also be triggered manually from GitHub Actions.

Dropbox app settings are available at `https://www.dropbox.com/developers/apps`.

Recommended Dropbox layout:

```text
/site-photo-inbox/
  iphone/
  street/
  portraits/
```

Upload photos into `site-photo-inbox/<category>/` from any device that can write to Dropbox.

The workflow will:

- download supported images from Dropbox into a temporary inbox
- run the existing ingest flow against that temporary inbox
- run tests and build the site
- commit and push any generated photo files and gallery pages
- remove successfully processed Dropbox files from the Dropbox inbox only after the workflow succeeds
- move rejected Dropbox files into a quarantine folder for manual review

Dropbox file lifecycle:

- The Dropbox sync workflow keeps one JSON state file for the current run. Each entry records the original Dropbox path and the temporary local source file. Ingest adds `status` only after it has decided the outcome.
- `ingested`: the file was imported successfully into the site. During finalize, it is removed from the Dropbox inbox.
- `skipped`: the file was rejected by ingest. During finalize, it is moved to the quarantine folder instead of being removed.

Finalize rules:

- if a state entry is `ingested`, remove the original Dropbox file from the inbox
- if a state entry is `skipped`, move the original Dropbox file to quarantine
- if any state entry is still missing `status`, stop instead of guessing

Current skip reasons written into Dropbox sync state or a standalone ingest results file:

- `missing-category`: the file was not inside a category folder.
- `missing-exif-datetimeoriginal`: the file does not have the required `EXIF:DateTimeOriginal` capture timestamp.

Required GitHub secrets:

- `DROPBOX_ACCESS_TOKEN`, or
- `DROPBOX_REFRESH_TOKEN` together with `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET`

Optional GitHub repository variables:

- `DROPBOX_INBOX_PATH` default `/site-photo-inbox`
- `DROPBOX_QUARANTINE_PATH` default `/site-photo-quarantine`

Notes:

- The Dropbox folder structure should match the existing category folders because category detection still comes from subdirectories.
- Files only leave the Dropbox inbox after a successful workflow run. Accepted files are removed from the Dropbox inbox; rejected files go to the quarantine folder.
- GitHub's `GITHUB_TOKEN` can push the commit back to the repository; that push is still visible to Cloudflare Pages for deployment.
