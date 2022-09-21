# syntax = docker/dockerfile:1
FROM python:3.8-slim as builder

ENV PYTHONUNBUFFERED 1

# Install poetry
RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Produce requirements.txt
WORKDIR /app
COPY poetry.lock pyproject.toml /app/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Produce wheel
COPY zbuilder /app/zbuilder
COPY README.md /app/
COPY LICENSE /app/
RUN poetry build

# Create final docker image
FROM python:3.8-slim

ENV PATH="${PATH}:/app/.local/bin"

RUN useradd -ms /bin/bash app -d /app -u 1001
USER app
WORKDIR /app

COPY --from=builder /app/requirements.txt /app
RUN pip install --user -r requirements.txt && rm requirements.txt

COPY --from=builder /app/dist/*.whl /app
RUN pip install --user *.whl && rm -rf *.whl

CMD ["zbuilder"]
