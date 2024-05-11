# Choose the Python version you want
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

# Create a working directory
WORKDIR /app

# Copy your FastAPI application
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Expose the port used by your application (usually 8000)
EXPOSE 8000

# Run the application using Uvicorn as the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "3"]