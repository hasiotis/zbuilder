.PHONY: help ## Print this help
help:
	@grep -E '^\.PHONY: [a-zA-Z_-]+ .*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = "(: |##)"}; {printf "\033[36m%-30s\033[0m %s\n", $$2, $$3}'


.PHONY: tests ## Run unit tests
tests:
	pytest --junit-xml=results.xml --cov=zbuilder --cov-fail-under=30 --color=yes tests/


.PHONY: style  ## Run unit tests
style:
	flake8 zbuilder


.PHONY: init ## Initialize pipenv for development
init:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	python setup.py develop


.PHONY: lock ## Lock requirements
lock:
	pipenv lock -r > requirements.txt
	pipenv lock -r -d > requirements-dev.txt


.PHONY: docs ## Generate documentation
docs:
	cd docs && make html


.PHONY: clean ## Cleanup generated files
clean:
	rm -rf *.egg-info build dist docs/_build zbuilder/zbuilder.1
	find . -type d -name __pycache__ -exec rm -r {} \+


.PHONY: release  ## Make release
release:
	bumpversion --commit --tag patch zbuilder/__init__.py
	python setup.py sdist bdist_wheel
	#twine upload dist/*


.PHONY: release-test  ## Make release on test pypi
release-test:
	python setup.py sdist bdist_wheel
	twine upload --repository-url https://test.pypi.org/legacy/ --repository zbuilder dist/*
