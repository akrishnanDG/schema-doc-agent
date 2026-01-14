FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY schema_doc_bot/ ./schema_doc_bot/
COPY pyproject.toml .
COPY setup.py .

# Install package
RUN pip install --no-cache-dir -e .

# Set default command
ENTRYPOINT ["python", "-m", "schema_doc_bot.cli"]
CMD ["--help"]

