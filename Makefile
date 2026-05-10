OUTPUT_DIR = output
INGEST_SRC ?= inbox
NOTEBOOK_SRC ?= notebooks/dummy_interactive.py
NOTEBOOK_OUT ?= content/notebooks/dummy_interactive.html

venv:
	uv sync

run:
	uv run pelican -s pelicanconf.py -t theme -o output -l -r

clean:
	rm -rf $(OUTPUT_DIR)

ingest:
	uv run python scripts/ingest_photos.py --src $(INGEST_SRC)

test:
	uv run pytest

export-notebook:
	uv tool run marimo export html $(NOTEBOOK_SRC) -o $(NOTEBOOK_OUT)

.PHONY: venv run clean ingest test export-notebook
