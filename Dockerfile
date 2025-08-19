FROM python:3.11-slim-bookworm

ENV PIP_NO_CACHE_DIR=1

# Install git and other needed tools
RUN apt-get update && apt-get install -y git gcc && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools

# Copy application code
WORKDIR /app
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["python", "-m", "TEAMZYRO"]