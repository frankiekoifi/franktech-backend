-- Drop existing tables if they exist
DROP TABLE IF EXISTS errors;

-- Create errors table
CREATE TABLE
    errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type VARCHAR(255),
        message TEXT NOT NULL,
        stack_trace TEXT,
        severity VARCHAR(20) DEFAULT 'error',
        url TEXT,
        line_no INTEGER,
        col_no INTEGER,
        user_id VARCHAR(255),
        user_email VARCHAR(255),
        environment VARCHAR(50),
        release_version VARCHAR(100),
        metadata JSON,
        status VARCHAR(20) DEFAULT 'unresolved',
        has_ai_analysis BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

-- Create indexes for performance
CREATE INDEX idx_errors_created_at ON errors (created_at DESC);

CREATE INDEX idx_errors_severity ON errors (severity);

CREATE INDEX idx_errors_status ON errors (status);