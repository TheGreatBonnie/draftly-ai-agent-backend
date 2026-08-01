-- Migration 005: Replace notification_channel with per-platform booleans
-- Allows reviewers to receive notifications on multiple platforms simultaneously.

-- Add per-platform notification booleans
ALTER TABLE reviewers ADD COLUMN notify_slack BOOL DEFAULT true;
ALTER TABLE reviewers ADD COLUMN notify_discord BOOL DEFAULT false;
ALTER TABLE reviewers ADD COLUMN notify_email BOOL DEFAULT false;

-- Migrate data from notification_channel
UPDATE reviewers SET notify_slack = true WHERE notification_channel = 'slack';
UPDATE reviewers SET notify_discord = true WHERE notification_channel = 'discord';
UPDATE reviewers SET notify_email = true WHERE notification_channel = 'email';

-- Drop old single-channel column
ALTER TABLE reviewers DROP COLUMN notification_channel;
