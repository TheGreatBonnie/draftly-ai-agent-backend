-- Migration 012: Add discord_trigger_channels to organizations
-- Stores array of channel IDs where the bot should respond to @mentions

ALTER TABLE organizations
ADD COLUMN IF NOT EXISTS discord_trigger_channels JSONB DEFAULT '[]'::jsonb;
