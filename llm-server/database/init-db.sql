-- Initialize Stockelper Database
-- This script creates the necessary databases and users for the Stockelper LLM server

-- Create checkpoint database for LangGraph state management
CREATE DATABASE checkpoint;

-- Grant permissions to stockelper user
GRANT ALL PRIVILEGES ON DATABASE stockelper TO stockelper;
GRANT ALL PRIVILEGES ON DATABASE checkpoint TO stockelper;

-- Connect to stockelper database and create extensions if needed
\c stockelper;

-- Create extensions for enhanced functionality
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Connect to checkpoint database and create extensions
\c checkpoint;

-- Create extensions for checkpoint database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create basic tables for checkpoint management (LangGraph will handle detailed schema)
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT PRIMARY KEY,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_type ON checkpoints(type);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoints(created_at);

-- Create writes table for LangGraph
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id ON checkpoint_writes(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_checkpoint_id ON checkpoint_writes(checkpoint_id);

-- Grant permissions on checkpoint tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO stockelper;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO stockelper;

-- Switch back to stockelper database for any additional setup
\c stockelper;

-- Grant permissions on stockelper tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO stockelper;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO stockelper;
