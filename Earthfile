VERSION 0.8
FROM python:3.12

uv:
    FROM ghcr.io/astral-sh/uv:latest
    SAVE ARTIFACT /uv

build:
    # Install uv
    COPY +uv/uv /usr/local/bin/uv

    # Add files
    COPY --dir zbuilder .
    COPY uv.lock pyproject.toml README.md LICENSE .

    # Install zbuilder
    RUN uv build
    RUN uv pip install --system dist/zbuilder-*.whl

    # Save for usage on docker
    SAVE ARTIFACT /usr/local/lib/python3.12/site-packages
    SAVE ARTIFACT /usr/local/bin/zbuilder

docker:
    ARG reg=localhost
    ARG tag=latest

    ENV PYTHONPATH=/usr/lib/python3/site-packages

    COPY +build/site-packages /usr/lib/python3/site-packages
    COPY +build/zbuilder /usr/bin/zbuilder

    CMD ["/usr/bin/zbuilder"]

    SAVE IMAGE --push $reg/zbuilder:$tag
