-- Schema for Audiobookshelf Listening History

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL
);

-- Devices Table
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY,
    client_name TEXT,
    device_name TEXT,
    model TEXT,
    manufacturer TEXT,
    client_version TEXT
);

-- Library Items Table (Books/Podcasts)
CREATE TABLE IF NOT EXISTS library_items (
    id UUID PRIMARY KEY,
    library_id UUID NOT NULL,
    media_type TEXT,
    title TEXT,
    author TEXT,
    description TEXT,
    genres TEXT[], -- Array of text
    release_date TIMESTAMP WITH TIME ZONE,
    feed_url TEXT,
    image_url TEXT,
    explicit BOOLEAN,
    language TEXT
);

-- Listening Sessions Table
CREATE TABLE IF NOT EXISTS listening_sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    library_item_id UUID REFERENCES library_items(id),
    episode_id UUID, -- distinct from item_id for podcasts
    device_id UUID REFERENCES devices(id),
    
    display_title TEXT,
    display_author TEXT,
    
    duration FLOAT,
    time_listening FLOAT,
    start_offset FLOAT, -- mapped from startTime
    media_progress FLOAT, -- mapped from currentTime
    
    started_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    
    date_log DATE, -- mapped from 'date' string if needed, or derived from started_at
    day_of_week TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON listening_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON listening_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_library_item_id ON listening_sessions(library_item_id);
