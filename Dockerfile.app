FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source folders and files
COPY app/ /app/app/
COPY scripts/ /app/scripts/
COPY Recursos_TS_Leon.db /app/Recursos_TS_Leon.db

EXPOSE 8001

# Start server using Gunicorn in production mode
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8001", "app.server:app"]
