PYTHON ?= python3
VENV ?= .venv

.PHONY: bootstrap clean

bootstrap: $(VENV)/bin/python
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -e ".[dev]"
	@echo "Done. Activate with: source $(VENV)/bin/activate"

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

clean:
	rm -rf $(VENV)
