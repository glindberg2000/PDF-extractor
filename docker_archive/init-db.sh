#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! pg_isready -h localhost -p 5432 -U postgres; do
    sleep 1
done

# Create database if it doesn't exist
echo "Creating database if it doesn't exist..."
psql -U postgres -h localhost -p 5432 -tc "SELECT 1 FROM pg_database WHERE datname = 'pdf_extractor'" | grep -q 1 || \
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE pdf_extractor"

# Create user if it doesn't exist
echo "Creating user if it doesn't exist..."
psql -U postgres -h localhost -p 5432 -tc "SELECT 1 FROM pg_user WHERE usename = 'postgres'" | grep -q 1 || \
psql -U postgres -h localhost -p 5432 -c "CREATE USER postgres WITH PASSWORD 'postgres'"

# Grant privileges
echo "Granting privileges..."
psql -U postgres -h localhost -p 5432 -c "GRANT ALL PRIVILEGES ON DATABASE pdf_extractor TO postgres"

echo "Database initialization complete!" 