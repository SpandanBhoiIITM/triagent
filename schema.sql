-- Run this once:  mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS ticketdb;
USE ticketdb;

CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50),            -- predicted by ML model
    sentiment VARCHAR(20),           -- positive / negative / neutral
    status VARCHAR(20) DEFAULT 'open',   -- open / needs_review / resolved
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),   -- interview point: speeds up WHERE category = ?
    INDEX idx_created (created_at),
    INDEX idx_status (status)        -- used by review queue and cleanup
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id VARCHAR(36) PRIMARY KEY,      -- uuid generated in python
    status VARCHAR(20) DEFAULT 'queued',   -- queued -> running -> done / failed
    query_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    INDEX idx_status (status)
);

CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,           -- final agent generated report
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id),
    INDEX idx_job (job_id)
);
