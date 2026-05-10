OUTPUT_DIR = output
INGEST_SRC ?= inbox

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

.PHONY: venv run clean ingest test
