-- 020: Allow 'escalated' status on support_threads so completed-but-unpublished
-- runs can be flagged for human follow-up (ADLC §4 Product metric).

ALTER TABLE support_threads DROP CONSTRAINT support_threads_status_check;
ALTER TABLE support_threads ADD CONSTRAINT support_threads_status_check
  CHECK (status IN ('open', 'processing', 'resolved', 'escalated'));
