VERSION 0.8
FROM python:3.11

build:
    # Install poetry
    RUN apt-get update && apt-get install -y curl
    RUN curl -sSL https://install.python-poetry.org | python3 -
    RUN ln -s /root/.local/bin/poetry /usr/local/bin/poetry

    # Add files
    COPY --dir zbuilder .
    COPY poetry.lock pyproject.toml README.md .

    # Install zbuilder
    RUN poetry build
    RUN pip3 install dist/zbuilder-*.whl

    # Save for usage on docker
    SAVE ARTIFACT /usr/local/lib/python3.11/site-packages
    SAVE ARTIFACT /usr/local/bin/zbuilder

docker:
    ENV PYTHONPATH=/usr/lib/python3/site-packages
    COPY +build/site-packages /usr/lib/python3/site-packages
    COPY +build/zbuilder /usr/bin/zbuilder
    CMD ["/usr/bin/zbuilder"]

    SAVE IMAGE zbuilder:latest
