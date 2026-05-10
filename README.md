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
