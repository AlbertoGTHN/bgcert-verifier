-- ICCBPO Certificate Checker - Initial Database Setup
-- This script runs once when the postgres container is first initialized

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fast text search

-- Ensure the database exists (already handled by POSTGRES_DB env var)

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE iccbpo_cert_checker TO iccbpo;
