# georgios-karakostas.com

My [personal website](https://www.georgios-karakostas.com) repository.

Made with [Pelican](https://github.com/getpelican/pelican). Deployed using [Cloudflare Pages](https://pages.cloudflare.com/).

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
uv run pelican -s pelicanconf.py -t theme -o output -l -r
uv run pytest
```

## Photo workflow

Drop new photos into `inbox/<category>/` and run:

```bash
make ingest
```

By default, ingest moves files out of `inbox/` into `content/images/photos/...` so the same photos are not re-imported on the next run.

This creates:

- `content/images/photos/<category>/<id>.<ext>`
- `content/images/photos/<category>/<id>.json`

Metadata JSON is auto-generated with date/category/id and can be edited later for `caption`, `location`, and `published`.

Any new category folder under `inbox/` (for example `inbox/macro/`) is automatically available as a browsable gallery page at `/<category>/` after ingest + build.

Useful options:

```bash
uv run python scripts/ingest_photos.py --src inbox
uv run python scripts/ingest_photos.py --src inbox --copy
uv run python scripts/ingest_photos.py --src inbox --category street
uv run python scripts/ingest_photos.py --src inbox --dry-run
```

## Dropbox uploads

The local `inbox/` workflow can stay in place alongside a second Dropbox-based upload path.

The `.github/workflows/dropbox-photo-sync.yml` workflow runs every 15 minutes and can also be triggered manually from GitHub Actions.

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
- run the existing ingest flow unchanged
- run tests and build the site
- commit and push any generated photo files and gallery pages
- move processed Dropbox files into an archive folder so they are not imported twice

Required GitHub secrets:

- `DROPBOX_ACCESS_TOKEN`, or
- `DROPBOX_REFRESH_TOKEN` together with `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET`

Optional GitHub repository variables:

- `DROPBOX_INBOX_PATH` default: `/site-photo-inbox`
- `DROPBOX_ARCHIVE_PATH` default: `/site-photo-archive`

Notes:

- The Dropbox folder structure should match the existing category folders because category detection still comes from subdirectories.
- If the workflow fails after downloading and archiving files, the originals will be in the Dropbox archive folder rather than the inbox.
- GitHub's `GITHUB_TOKEN` can push the commit back to the repo; that push will still be visible to Cloudflare Pages for deployment.
