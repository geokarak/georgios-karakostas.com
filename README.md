# georgios-karakostas.com

Source for [georgios-karakostas.com](https://www.georgios-karakostas.com), a
Pelican site deployed via [Cloudflare Pages](https://pages.cloudflare.com/).
Runtime vendor assets are checked into `theme/static/vendor/` so the published
site does not depend on third-party CDNs for MathJax, Vega, or GLightbox.

## Development

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
make venv       # install project and development dependencies
make run        # serve the site locally with live reload
make test       # run tests
make check      # verify lockfile, lint, and formatting
```

Photo ingestion additionally requires `exiftool`. Place images in category
subfolders under `inbox/`, then run `make ingest`. See
[`docs/INGEST_PHOTOS_FLOW.md`](docs/INGEST_PHOTOS_FLOW.md) for the ingest details
and [`docs/SYNC_DROPBOX_INBOX_FLOW.md`](docs/SYNC_DROPBOX_INBOX_FLOW.md) for the
automated Dropbox workflow.

CI builds the production configuration with `publishconf.py` and runs the code
checks and tests.
