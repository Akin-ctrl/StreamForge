SHELL := /bin/bash

CONTROL_PLANE_PYTHON := control-plane/.venv/bin/python

.PHONY: standards-gate control-plane-dev-deps control-plane-test runtime-test adapters-test sinks-test ui-build verify

standards-gate:
	bash scripts/check_standards_gates.sh

control-plane-dev-deps:
	test -x "$(CONTROL_PLANE_PYTHON)"
	"$(CONTROL_PLANE_PYTHON)" -m pip install -r control-plane/requirements-dev.txt

control-plane-test:
	test -x "$(CONTROL_PLANE_PYTHON)"
	cd control-plane && .venv/bin/python -m pytest tests

runtime-test:
	python3 -m unittest discover -s gateway_runtime/tests

adapters-test:
	python3 -m unittest discover -s adapters/tests

sinks-test:
	python3 -m unittest discover -s sinks/tests

ui-build:
	cd ui && npm run build

verify: standards-gate control-plane-test runtime-test adapters-test sinks-test ui-build
