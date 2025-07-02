FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/

# Set Python path
ENV PYTHONPATH=/app

# Expose port for local development
EXPOSE 8000

# Command for local development
CMD ["uvicorn", "src.handlers.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]