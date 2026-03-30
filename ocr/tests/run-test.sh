#!/bin/bash

# Script to run the AI department selection test with Docker

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}OCR Server AI Test Runner${NC}"
echo "================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

echo -e "${YELLOW}Docker image not found, building Docker image...${NC}"
docker build -f Dockerfile -t ocr-server . || {
    echo -e "${RED}Error: Failed to build Docker image${NC}"
    exit 1
}

# Run the test
echo -e "${YELLOW}Running AI department selection test...${NC}"
echo ""

docker run --rm \
    --env-file ../.env \
    -v $(pwd):/app \
    -w /app \
    ocr-server python ./tests/test-ai-csv.py ./tests/data/test_cases.csv

echo ""
echo -e "${GREEN}Test completed!${NC}"
