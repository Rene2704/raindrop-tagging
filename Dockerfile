# Use Python 3.11 slim image as base
FROM python:3.12.7


# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the application
CMD ["python", "-m", "raindrop_information_extaction.main"]