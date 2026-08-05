-- 019: Backfill remaining NULL embeddings.org_id from source tables, drop true
-- orphans, then enforce NOT NULL. Idempotent: after the first run there are no
-- NULL rows, so steps 1-2 are no-ops and step 3 is already satisfied.

-- 1. Backfill from source tables by content_id
UPDATE embeddings e
SET org_id = COALESCE(
    (SELECT d.org_id FROM documentation d WHERE d.id::text = e.content_id),
    (SELECT s.org_id FROM support_threads s WHERE s.id::text = e.content_id),
    e.org_id
)
WHERE e.org_id IS NULL
  AND e.content_type IN ('documentation', 'support_threads');

-- 2. Delete true orphans (no recoverable org; unreachable by any search path)
DELETE FROM embeddings WHERE org_id IS NULL;

-- 3. Enforce the invariant going forward
ALTER TABLE embeddings ALTER COLUMN org_id SET NOT NULL;
