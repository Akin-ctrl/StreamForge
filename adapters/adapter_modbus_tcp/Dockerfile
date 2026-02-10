FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY adapter_modbus_tcp/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY adapter_modbus_tcp /app/adapters/adapter_modbus_tcp
COPY adapter_base /app/adapters/adapter_base
COPY __init__.py /app/adapters/__init__.py

CMD ["python", "-m", "adapters.adapter_modbus_tcp.main"]
