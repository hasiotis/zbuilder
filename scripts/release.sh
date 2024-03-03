#!/bin/bash

READTHEDOCS_URL="https://readthedocs.org/api/v3/projects/zbuilder/versions/master/builds/"

OLD_VERSION=`poetry version -s`
poetry version patch
NEW_VERSION=`poetry version -s`

git add pyproject.toml
git commit -m "Bump version from v${OLD_VERSION} to v${NEW_VERSION}"
git push
git tag -a "release-v${NEW_VERSION}" -m "Version v${NEW_VERSION}"
git push --tags

poetry publish -n --build -u __token__ -p ${POETRY_PYPI_TOKEN_PYPI}
rm -rf dist/*

http -b POST ${READTHEDOCS_URL} "Authorization:Token ${READTHEDOCS_TOKEN}" | jq .builds.urls.build
