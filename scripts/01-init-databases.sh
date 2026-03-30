#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create MLflow database
    CREATE DATABASE mlflow_db;
    GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO $POSTGRES_USER;
    \l
EOSQL

echo "Multiple databases initialized successfully!"
