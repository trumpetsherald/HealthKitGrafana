FROM python:3.8.11-alpine

ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /opt

WORKDIR /opt/healthkit_grafana

COPY requirements.txt .

RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
 python3 -m pip install -r requirements.txt --no-cache-dir && \
 apk --purge del .build-deps

RUN mkdir -p /opt/healthkit_grafana/apple_health_export
ADD healthkit_grafana /opt/healthkit_grafana

CMD ["python3", "health_kit_grafana.py"]
