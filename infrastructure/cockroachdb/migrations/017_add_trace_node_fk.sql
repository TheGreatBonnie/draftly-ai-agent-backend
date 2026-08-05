-- 017: Add FK from agent_trace_nodes.trace_id to agent_traces.id (ON DELETE CASCADE).
-- agent_trace_nodes.trace_id has NO FK: the retention purge deletes agent_traces rows,
-- orphaning node rows forever. The pre-cleanup DELETE makes the FK add safe on existing
-- data with orphans. The FK lives only here (schema.sql does not define agent_traces —
-- that table comes from migration 013).

DELETE FROM agent_trace_nodes
WHERE trace_id IS NOT NULL AND trace_id NOT IN (SELECT id FROM agent_traces);

ALTER TABLE agent_trace_nodes
ADD CONSTRAINT agent_trace_nodes_trace_id_fkey
FOREIGN KEY (trace_id) REFERENCES agent_traces(id) ON DELETE CASCADE;
