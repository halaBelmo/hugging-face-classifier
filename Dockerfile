FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000 8265 5000

CMD ["sh", "-c", "python -m madewithml.serve --host 0.0.0.0 --run_id ${RUN_ID:?RUN_ID is required}"]
