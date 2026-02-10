FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY gateway_runtime/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY gateway_runtime /app/gateway_runtime
COPY adapters /app/adapters

CMD ["python", "-m", "gateway_runtime.main"]
