.PHONY: help ## Print this help
help:
	@grep -E '^\.PHONY: [a-zA-Z_-]+ .*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = "(: |##)"}; {printf "\033[36m%-30s\033[0m %s\n", $$2, $$3}'


.PHONY: init ## Initialize for development
init:
	@poetry install
	@poetry run pre-commit install


.PHONY: docs ## Generate documentation
docs:
	@cd docs && make html


.PHONY: clean ## Cleanup generated files
clean:
	@rm -rf *.egg-info build dist docs/_build .coverage results.xml
	@find . -type d -name __pycache__ -exec rm -r {} \+


.PHONY: release  ## Make release
release:
	echo $(shell "poetry version")
	#poetry version patch
	#VERSION := $(shell poetry -s version)
	#echo $(VERSION)
	#@git add pyproject.toml
	#@git commit -m "Bump version: 0.0.29 → 0.0.30"
	#@poetry build
	#@poetry publish --dry-run
	rm -rf dist/*
	#curl -X POST -s -o /dev/null -w "%{http_code}"      \
	#		-H "Authorization: Token ${READTHEDOCS_TOKEN}"  \
	#	-H "Content-Type: application/json"             \
	#		https://readthedocs.org/api/v3/projects/zbuilder/versions/master/builds/ -d ""


.PHONY: pre-release  ## Make pre release
pre-release:
	@poetry version prerelease
	@poetry build
	#@poetry publish -r https://test.pypi.org/legacy/
	rm -rf dist/*
