CREATE TABLE players ();
CREATE TABLE _migrations ();
ALTER TABLE players ADD COLUMN username VARCHAR(32);
ALTER TABLE players ADD COLUMN status INTEGER;
ALTER TABLE _migrations ADD COLUMN id_ INTEGER;
ALTER TABLE players ALTER COLUMN username SET NOT NULL;
ALTER TABLE players ALTER COLUMN status SET NOT NULL;
ALTER TABLE _migrations ALTER COLUMN id_ SET NOT NULL;
ALTER TABLE players ADD CONSTRAINT _players_username_primary_key PRIMARY KEY ( username );
ALTER TABLE _migrations ADD CONSTRAINT __migrations_id__primary_key PRIMARY KEY ( id_ );