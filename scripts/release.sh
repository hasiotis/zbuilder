#!/bin/bash

READTHEDOCS_URL="https://readthedocs.org/api/v3/projects/zbuilder/versions/master/builds/"

OLD_VERSION=`uv version --short`
uv version --bump patch
NEW_VERSION=`uv version --short`

git add pyproject.toml uv.lock
git commit -m "Bump version from v${OLD_VERSION} to v${NEW_VERSION}"
git push
git tag -a "v${NEW_VERSION}" -m "Version v${NEW_VERSION}"
git push --tags

uv build
uv publish -u __token__ -p ${UV_PUBLISH_TOKEN}
rm -rf dist/*

http -b POST ${READTHEDOCS_URL} "Authorization:Token ${READTHEDOCS_TOKEN}" | jq -r .build.urls.build
