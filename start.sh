#!/bin/bash
set -e

echo "========================================"
echo "Starting Hermes Agent Cloud..."
echo "========================================"

# Create Hermes home directory
mkdir -p ~/.hermes/skills ~/.hermes/plugins ~/.hermes/cron ~/.hermes/sessions

# Set environment
export HERMES_HOME=/app/.hermes
export DATA_DIR=/app/data

# Check required variables
if [ -z "$OPENAI_API_KEY" ] && [ -z "$OLLAMA_API_KEY" ] && [ -z "$OPENROUTER_API_KEY" ]; then
    echo "WARNING: No API key set. Set OPENAI_API_KEY, OLLAMA_API_KEY, or OPENROUTER_API_KEY"
fi

# Start the web interface
echo "Starting Hermes Web Interface on port 10000..."
exec python3 /app/main.py