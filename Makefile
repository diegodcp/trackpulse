.PHONY: setup up down lint typecheck test e2e

setup:
	@echo "TODO: install project dependencies"

up:
	@echo "TODO: start local infrastructure"

down:
	@echo "TODO: stop local infrastructure"

lint:
	@echo "TODO: run linters"

typecheck:
	@echo "TODO: run type checks"

test:
	@echo "TODO: run unit and integration tests"

e2e:
	cd apps/web && npm run test:e2e
