FROM python:slim

RUN mkdir /app
COPY sensor /app/sensor
COPY common /app/common
COPY requirements.txt /app

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache \
    if [ -f sensor/requirements.txt ]; then \
        pip install -r sensor/requirements.txt; \
    fi

ENV PYTHONPATH "${PYTHONPATH}:/app"
ENTRYPOINT ["python", "sensor/main.py"]
