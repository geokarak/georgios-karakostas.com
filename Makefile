VENV_DIR := .venv
VENV_PIP := $(VENV_DIR)/bin/pip
OUTPUT_DIR = output

venv:
	rm -rf $(VENV_DIR)
	python -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt

run:
	pelican -s pelicanconf.py -t theme -o output -l -r

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: venv run clean