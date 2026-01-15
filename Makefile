VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)
	$(PIP) install -r server/requirements.txt

server-dev:
	$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir server

test:
	$(PY) -m pytest server/app/tests

seed-reference:
	$(PY) scripts/seed_references.py --ref $(REF) --doc-type "$(DOC_TYPE)" --version "$(VERSION)" --metadata '$(METADATA)'

mobile-run:
	$(PIP) install -r mobile/requirements.txt
	$(PY) mobile/main.py
