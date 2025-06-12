# Use an official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port Functions Framework uses
ENV PORT 8080

# Launch the app via Functions Framework
CMD ["functions-framework", "--target", "app", "--port", "8080"]
