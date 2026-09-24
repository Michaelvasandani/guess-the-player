# Soccerdle

A Wordle-style game: guess the mystery footballer in **5 tries**. There are no letter clues. Each guess
is compared to the mystery player, and what they have in common is the clue:

| Column  | Green | Yellow | Grey |
|---------|-------|--------|------|
| Nation  | same nationality | same continent | — |
| Pos     | same position (e.g. Centre-Back) | same line (e.g. another defender) | — |
| Leagues | same set of leagues | some overlap (faded = not shared) | none shared |
| Clubs   | correct player | played for ≥1 of the same clubs (shared ones highlighted under the row) | none shared |
| Born    | same year | within 2 years (↑ later / ↓ earlier) | further away |

The player pool is everyone who played in the Premier League, La Liga, Serie A, Bundesliga or Ligue 1 from
2010/11 on (~12k players). Only well-known players are picked as the mystery player: peak market value
≥ €20m plus real top-5 minutes.

## Stack

- **PostgreSQL**: `players`, `clubs`, `leagues`, `player_clubs` (see [db/schema.sql](db/schema.sql))
- **Server**: plain Node `http` plus `pg`, with no framework ([server/index.js](server/index.js))
- **Frontend**: vanilla HTML/CSS/JS ([public/](public))
- **ETL**: Python ([etl/build.py](etl/build.py))

## Running locally

Requires Node ≥ 20.11, Python ≥ 3.10 and PostgreSQL binaries on your `PATH` (Postgres.app or Homebrew).

```sh
npm install
npm run db:start            # creates/starts a project-local cluster in .pgdata on port 5433

python3 -m venv etl/.venv
etl/.venv/bin/pip install -r etl/requirements.txt
npm run etl                 # downloads, scrapes and loads the data (first run ~30 min, then cached)

npm start                   # http://localhost:3000
```

`npm run db:stop` stops Postgres. `sh scripts/db.sh psql` opens a SQL shell.

To use an existing Postgres instead, set `DATABASE_URL` for both the ETL and the server, for example
`DATABASE_URL=postgresql://user:pass@localhost:5432/soccerdle`. The database needs the `unaccent`
extension, which ships with standard Postgres.

## Data

FBref blocks automated access (Cloudflare 403), so the data comes from Transfermarkt:

1. **[transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets)**: player profiles,
   every appearance since 2012/13, and transfer histories.
2. **Transfermarkt squad pages for 2010/11 and 2011/12**: covers players the dataset misses
   because their top-5 careers ended before 2012 (e.g. Nesta, Raúl, Del Piero).
3. **Transfermarkt's transfer-history endpoint**: full club histories for players the dataset has
   no transfers for.

"Clubs played for" is the union of clubs from transfer histories, appearances and squad lists. Youth,
reserve and "B" teams are filtered out. A club's league is the league it played league games in.
All HTTP responses are cached in `etl/.cache/`, so re-running the ETL is fast.

### Known gaps

- Club histories rely on Transfermarkt. A few obscure lower-league moves may be missing.
- Leagues outside the ~30 the dataset covers (e.g. Chinese Super League, Qatar) don't show in the Leagues column.
  The clubs still show in the club list.
- Mystery eligibility uses market value, so some legends whose peak predates Transfermarkt's values
  can be guessed but won't be picked as the answer.
