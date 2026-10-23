-- A demo workspace for showing the finance dashboard before a city's real exports arrive. It holds only the
-- fictional sample files (Lynn Haven's real FY2026 budget with invented spending, payments and bank figures),
-- so it is kept apart from the real Lynn Haven workspace. Same thresholds and audit findings as 'lh'.
insert into finance.workspaces (id, government_key, name, settings)
select 'lh-sample', 'lh', 'Lynn Haven (sample data)', settings from finance.workspaces where id = 'lh'
on conflict (id) do nothing;

insert into finance.members (workspace_id, email, role) values ('lh-sample', 'jeremy@fluxlabs.net', 'owner')
on conflict (workspace_id, email) do nothing;

insert into finance.audit_findings (workspace_id, fiscal_year, finding_id, title, topic, repeat, mgmt_response, source_url)
select 'lh-sample', fiscal_year, finding_id, title, topic, repeat, mgmt_response, source_url from finance.audit_findings where workspace_id = 'lh'
on conflict (workspace_id, fiscal_year, finding_id) do nothing;
