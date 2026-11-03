-- Alert sign-up by area and type (BayCounty.me alerts, phase 2).
-- account.prefs.alert_areas: governments whose notices a resident follows ('all' = the whole county; empty = follow the
--   saved home's city and zone, as before). quiet_hours: standard alerts arrive silently 10 PM to 7 AM.
-- push.devices.quiet: copied from the account so the sender can tell without a join.
-- Every phone and email list that asked for evacuation orders also gets the new public-safety switch turned on.
alter table account.prefs add column if not exists alert_areas text[] not null default '{}';
alter table account.prefs add column if not exists quiet_hours boolean not null default false;
alter table push.devices add column if not exists quiet boolean not null default false;

update account.prefs set push_topics = push_topics || array['safety']
  where 'evacuation' = any(push_topics) and not ('safety' = any(push_topics));
update account.prefs set alert_email = alert_email || array['safety']
  where 'evacuation' = any(alert_email) and not ('safety' = any(alert_email));
update push.devices set topics = topics || array['safety']
  where 'evacuation' = any(topics) and not ('safety' = any(topics));
alter table account.prefs alter column push_topics set default array['weather', 'evacuation', 'safety', 'shelters', 'water', 'agenda'];
alter table account.prefs alter column alert_email set default array['evacuation', 'safety', 'water'];
