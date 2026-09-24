#!/bin/sh
# Project-local Postgres cluster (data in ./.pgdata, port 5433, user/password wordle/wordle).
# Uses whatever initdb/pg_ctl is on PATH (Homebrew or Postgres.app both work).
set -e
cd "$(dirname "$0")/.."
PGDATA=.pgdata
PORT=${PGPORT:-5433}

case "$1" in
  start)
    if [ ! -d "$PGDATA" ]; then
      echo "wordle" > .pgpass.tmp
      initdb -D "$PGDATA" -U wordle --auth=scram-sha-256 --pwfile=.pgpass.tmp -E UTF8 --locale=C > /dev/null
      rm .pgpass.tmp
      pg_ctl -D "$PGDATA" -o "-p $PORT -k /tmp" -l "$PGDATA/server.log" -w start
      PGPASSWORD=wordle psql -h localhost -p "$PORT" -U wordle -d postgres -qc "CREATE DATABASE soccerdle"
    elif pg_ctl -D "$PGDATA" status > /dev/null 2>&1; then
      echo "Postgres already running on port $PORT"
    else
      pg_ctl -D "$PGDATA" -o "-p $PORT -k /tmp" -l "$PGDATA/server.log" -w start
    fi
    ;;
  stop) pg_ctl -D "$PGDATA" -w stop ;;
  psql) PGPASSWORD=wordle psql -h localhost -p "$PORT" -U wordle soccerdle ;;
  *) echo "usage: $0 start|stop|psql"; exit 1 ;;
esac
