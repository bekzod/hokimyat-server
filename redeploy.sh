#!/bin/bash
set -e

# Pull the latest changes
git pull origin master

# Build and restart the Docker Compose stack
docker-compose down
docker-compose up -d --build
