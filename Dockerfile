# Match local venv: Python 3.12
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY vendor/ vendor/
RUN pip install --no-cache-dir --no-deps -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]