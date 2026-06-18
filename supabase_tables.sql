-- Memory table
CREATE TABLE IF NOT EXISTS memory (
    id SERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    messages JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Skills table
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE memory ENABLE ROW LEVEL SECURITY;
alter table sessions enable row level security;
ALTER TABLE skills ENABLE ROW LEVEL SECURITY;

-- Create policies for anon key
CREATE POLICY "Allow anon read" ON memory FOR SELECT USING (true);
CREATE POLICY "Allow anon insert" ON memory FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update" ON memory FOR UPDATE USING (true);

CREATE POLICY "Allow anon read" ON sessions FOR SELECT USING (true);
CREATE POLICY "Allow anon insert" ON sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update" ON sessions FOR UPDATE USING (true);

CREATE POLICY "Allow anon read" ON skills FOR SELECT USING (true);
CREATE POLICY "Allow anon insert" ON skills FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update" ON skills FOR UPDATE USING (true);