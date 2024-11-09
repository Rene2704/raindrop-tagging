# Build the image
docker build -t raindrop-extractor .

# Run with environment variables
docker run -v $(pwd)/logs:/app/logs --env-file .env raindrop-extractor