FROM python:alpine

RUN mkdir /app
COPY proxy /app/proxy
COPY common /app/common
COPY requirements.txt /app

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache \
    if [ -f proxy/requirements.txt ]; then \
        pip install -r proxy/requirements.txt; \
    fi

ENV PYTHONPATH "${PYTHONPATH}:/app"
ENTRYPOINT ["python", "proxy/main.py"]
