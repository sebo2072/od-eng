FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Tell Docker (and readers) we listen on 8080
EXPOSE 8080
ENV PORT 8080

# Launch with a 240 s timeout, binding to all interfaces
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--timeout", "240", "main:app"]
