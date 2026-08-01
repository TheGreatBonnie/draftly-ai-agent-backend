-- 010: Slack conversation history for thread-aware bot responses
CREATE TABLE IF NOT EXISTS slack_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    channel_id STRING NOT NULL,
    thread_ts STRING NOT NULL,
    role STRING NOT NULL CHECK (role IN ('user', 'assistant')),
    content STRING NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_slack_conversations_lookup
    ON slack_conversations (channel_id, thread_ts, created_at);

CREATE INDEX IF NOT EXISTS idx_slack_conversations_cleanup
    ON slack_conversations (created_at);
