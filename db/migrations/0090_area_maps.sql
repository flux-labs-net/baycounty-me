-- Map areas on staff alerts and notices: where a boil-water notice, main break, road closure or other alert applies.
-- Stored as GeoJSON text (a FeatureCollection of pins with a radius, street lines and drawn areas), checked by
-- api/_gov.js areaShape(). Rows read from records leave it empty.
alter table gov.alerts add column if not exists geometry text;
alter table public_notices add column if not exists geometry text;
-- The live emergency feed carries the shape so /emergency and the apps can draw it.
alter table emergency_live add column if not exists geometry text;
