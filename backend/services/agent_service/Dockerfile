ARG SERVICE_NAME
FROM python:3.11-slim AS builder
ARG SERVICE_NAME
WORKDIR /app
COPY common/ ./common/
COPY services/${SERVICE_NAME}/requirements.txt ./service/
RUN pip install --no-cache-dir -r service/requirements.txt

FROM python:3.11-slim AS runtime
ARG SERVICE_NAME
WORKDIR /app
RUN apt-get update -qq && apt-get install -y -qq curl > /dev/null && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY common/ ./common/
COPY services/${SERVICE_NAME}/ ./service/
EXPOSE 8000
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]
