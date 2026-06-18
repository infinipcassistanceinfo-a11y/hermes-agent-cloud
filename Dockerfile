FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Hermes Agent
RUN pip install hermes-agent

# Create Hermes directories
RUN mkdir -p /app/.hermes/skills /app/.hermes/plugins /app/.hermes/cron /app/.hermes/sessions /app/data

# Copy application files
COPY main.py .
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 10000

CMD ["./start.sh"]