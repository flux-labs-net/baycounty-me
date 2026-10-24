-- Bulk review on /admin: shared-owner groups record who reviewed them and when, like the other review queues
-- (board_official_matches, careers.matches, limit_cases). Every review is also written to apiadmin.audit.
alter table registry.shared_owner_groups add column if not exists reviewed_by text;
alter table registry.shared_owner_groups add column if not exists reviewed_at timestamptz;
