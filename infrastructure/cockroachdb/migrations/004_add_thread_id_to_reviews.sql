-- Migration 004: Add thread_id to review_sessions for HITL resume
-- The thread_id stores the LangGraph checkpointer thread_id so the graph
-- can be resumed after interrupt() in human_review_node.

ALTER TABLE review_sessions ADD COLUMN thread_id STRING;

CREATE INDEX IF NOT EXISTS idx_review_thread ON review_sessions(thread_id);
