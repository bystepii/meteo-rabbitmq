FROM python:slim

RUN mkdir /app
COPY server /app/server
COPY common /app/common
COPY requirements.txt /app

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache \
    if [ -f server/requirements.txt ]; then \
        pip install -r server/requirements.txt; \
    fi

ENV PYTHONPATH "${PYTHONPATH}:/app"
ENTRYPOINT ["python", "server/main.py"]
