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
	#MSG=`poetry version patch`
	#git add pyproject.toml
	#git commit -m "${MSG}"
	#VER=`poetry version -s`
	#git tag -a v${VER} -m "Tagged version ${VER}"
	#poetry build
	#poetry publish -u hasiotis -p ${PASS}
	rm -rf dist/*
	#curl -X POST -s -o /dev/null -w "%{http_code}"      \
	#		-H "Authorization: Token ${READTHEDOCS_TOKEN}"  \
	#	-H "Content-Type: application/json"             \
	#		https://readthedocs.org/api/v3/projects/zbuilder/versions/master/builds/ -d ""
