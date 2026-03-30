FROM python:3.12-slim-bookworm

# Disable Python cache and set unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# ENV PYTHONPATH=/app

# Install curl for Docker health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the entire app code to /app in the container
COPY . /app
WORKDIR /app/

# Default command to run Uvicorn on startup
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
