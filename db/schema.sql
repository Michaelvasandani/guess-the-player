-- Soccerdle schema. Recreated from scratch on every ETL run.
CREATE EXTENSION IF NOT EXISTS unaccent;

DROP TABLE IF EXISTS player_clubs, players, clubs, leagues CASCADE;

CREATE TABLE leagues (
  id   text PRIMARY KEY,          -- Transfermarkt competition id, e.g. GB1
  name text NOT NULL
);

CREATE TABLE clubs (
  id        integer PRIMARY KEY,  -- Transfermarkt club id
  name      text NOT NULL,
  league_id text REFERENCES leagues(id)
);

CREATE TABLE players (
  id               integer PRIMARY KEY,  -- Transfermarkt player id
  name             text NOT NULL,
  search_name      text,                 -- lower(unaccent(name)), for autocomplete
  nationality      text NOT NULL,
  flag             text,
  continent        text NOT NULL,
  position         text NOT NULL,        -- Goalkeeper / Defender / Midfield / Attack
  sub_position     text NOT NULL,        -- e.g. Centre-Back, Left Winger
  birth_date       date,
  image_url        text,
  peak_value_eur   bigint NOT NULL DEFAULT 0,
  top5_minutes     integer NOT NULL DEFAULT 0,
  last_top5_year   integer,
  mystery_eligible boolean NOT NULL DEFAULT false
);

CREATE TABLE player_clubs (
  player_id  integer REFERENCES players(id) ON DELETE CASCADE,
  club_id    integer REFERENCES clubs(id),
  first_seen date,
  last_seen  date,
  PRIMARY KEY (player_id, club_id)
);

CREATE INDEX players_search_idx ON players (search_name text_pattern_ops);
CREATE INDEX players_mystery_idx ON players (id) WHERE mystery_eligible;
CREATE INDEX player_clubs_club_idx ON player_clubs (club_id);
