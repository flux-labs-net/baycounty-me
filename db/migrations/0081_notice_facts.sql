-- Readable public notices (site/longtext.py): the text now has blank lines between paragraphs, and four new columns on
-- public_notices hold the key facts pulled out of it for the top of the card on the site and in the apps.
-- reference: the bid, RFQ, ordinance or resolution number ("Bid PCB27-07"). emails, phones, links: every email address,
-- phone number and web address in the text, '; '-separated.
alter table public_notices add column if not exists "reference" text;
alter table public_notices add column if not exists "emails" text;
alter table public_notices add column if not exists "phones" text;
alter table public_notices add column if not exists "links" text;
