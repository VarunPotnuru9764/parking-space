FROM python:3.13-slim

WORKDIR /app
COPY detection/cloud_run_trigger/requirements.txt requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY detection/cloud_run_trigger/main.py main.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
