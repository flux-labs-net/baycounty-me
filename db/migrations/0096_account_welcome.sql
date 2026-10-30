-- New accounts get one welcome email (api/_account.js sendWelcome) with a link to join the countywide weekly email.
-- It is logged in account.sends like the other account emails, so it goes out once per account.
alter table account.sends drop constraint if exists sends_kind_check;
alter table account.sends add constraint sends_kind_check check (kind in ('weekly', 'alert', 'welcome'));
