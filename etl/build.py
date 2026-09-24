"""
Build the Soccerdle player database.

Sources
  1. transfermarkt-datasets (github.com/dcaribou/transfermarkt-datasets): player profiles,
     appearances since 2012/13 and transfer histories.
  2. Transfermarkt squad pages for 2010/11 and 2011/12, which the dataset does not cover.
  3. Transfermarkt's transfer-history endpoint, for players the dataset has no transfers for.

Every HTTP response is cached under etl/.cache, so re-runs are fast and offline-friendly.

Usage:  python etl/build.py [--skip-fetch]
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg
import requests
from bs4 import BeautifulSoup

from countries import lookup

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
DATASET_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/{}.csv.gz"
TM = "https://www.transfermarkt.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://wordle:wordle@localhost:5433/soccerdle")

TOP5 = {"GB1": "premier-league", "ES1": "laliga", "IT1": "serie-a", "L1": "1-bundesliga", "FR1": "ligue-1"}
EARLY_SEASONS = [2010, 2011]  # Transfermarkt season ids: 2010 = 2010/11

LEAGUE_NAMES = {
    "GB1": "Premier League", "ES1": "La Liga", "IT1": "Serie A", "L1": "Bundesliga", "FR1": "Ligue 1",
    "NL1": "Eredivisie", "PO1": "Liga Portugal", "TR1": "Süper Lig", "SC1": "Scottish Premiership",
    "BE1": "Belgian Pro League", "RU1": "Russian Premier League", "UKR1": "Ukrainian Premier League",
    "GR1": "Greek Super League", "DK1": "Danish Superliga", "A1": "Austrian Bundesliga",
    "C1": "Swiss Super League", "KR1": "Croatian HNL", "TS1": "Czech First League", "PL1": "Ekstraklasa",
    "RO1": "Romanian Superliga", "SER1": "Serbian SuperLiga", "SE1": "Allsvenskan", "NO1": "Eliteserien",
    "MLS1": "MLS", "SA1": "Saudi Pro League", "BRA1": "Brasileirão", "ARG1": "Argentine Primera",
    "MEX1": "Liga MX", "JAP1": "J1 League", "RSK1": "K League 1", "AUS1": "A-League",
}

BROAD_POSITION = {
    "Goalkeeper": "Goalkeeper",
    "Centre-Back": "Defender", "Left-Back": "Defender", "Right-Back": "Defender",
    "Defensive Midfield": "Midfield", "Central Midfield": "Midfield", "Attacking Midfield": "Midfield",
    "Left Midfield": "Midfield", "Right Midfield": "Midfield",
    "Left Winger": "Attack", "Right Winger": "Attack", "Centre-Forward": "Attack", "Second Striker": "Attack",
}

# Youth, reserve and placeholder "clubs" that shouldn't count as clubs played for.
# Transfermarkt truncates names to ~15 chars, hence patterns like "Yout" and "Aca".
NOT_A_CLUB = re.compile(
    r"(\bU\d{2,3}\b|\bM-\d{2}\b|Sub-?\d{2}|\bYth\.?|\bY(o(u(t(h)?)?)?)?\.?$|Youth|Jgd\.?|Jugend|Jeugd|Juvenil|"
    r"Juniors?\b|\bAca(d(emy)?)?\.?$|Academy|Acad\.|Primavera|Reserves?\b|\bRes\.$|\bFor(mation)?\.?$|"
    r"\bAtl\.$|^Atl\. (Madrileño|Levante|Malagueño)|\bProm$|^Jong |Futuro$|Ilicitano|^Betis Deportivo$|Amat(eure|\.)|"
    r"\bB$|\bC$|\bII$|\bIII$|Castilla|Next Gen|\bJV\b|Without Club|Retired|Career break|Unknown|Ban\b|"
    r"^(Bilbao Athletic|CD Basconia|Rayo Cantabria|Murcia Imperial|Oviedo Vetusta|Balón de Cádiz|Dep\. Fabril|"
    r"Barça Atlètic|Right to Dream|Diambars FC|JMG Bamako|ASPIRE FD|Academia Hagi)$|^Free agent)", re.I)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"})


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------- fetching

def fetch(url, cache_path, min_delay=0.4, retries=5):
    """GET url with an on-disk cache and polite backoff. Returns text, or None on 404."""
    cache_path = CACHE / cache_path
    if cache_path.exists():
        return cache_path.read_text()
    for attempt in range(retries):
        time.sleep(min_delay)
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(r.text)
            return r.text
        if r.status_code == 404:
            return None
        time.sleep(2 ** attempt * 2)  # 403/429/5xx: back off
    log(f"  ! giving up on {url}")
    return None


def download_dataset():
    out = {}
    for name in ["players", "clubs", "appearances", "transfers"]:
        path = CACHE / "dataset" / f"{name}.csv.gz"
        if not path.exists():
            log(f"downloading {name}.csv.gz")
            path.parent.mkdir(parents=True, exist_ok=True)
            r = session.get(DATASET_URL.format(name), timeout=300)
            r.raise_for_status()
            path.write_bytes(r.content)
        out[name] = pd.read_csv(path, low_memory=False)
    return out


def parse_money(s):
    m = re.match(r"€([\d.]+)(bn|m|k|Th\.)?", (s or "").strip())
    if not m:
        return None
    mult = {"bn": 1e9, "m": 1e6, "k": 1e3, "Th.": 1e3}.get(m.group(2), 1)
    return int(float(m.group(1)) * mult)


def scrape_early_squads():
    """Players registered to top-5 league squads in the seasons before the dataset starts."""
    rows = []
    for season in EARLY_SEASONS:
        for league, slug in TOP5.items():
            html = fetch(f"{TM}/{slug}/startseite/wettbewerb/{league}/plus/?saison_id={season}",
                         f"tm/league/{league}_{season}.html")
            soup = BeautifulSoup(html, "lxml")
            clubs = {}
            for a in soup.select('table.items td.hauptlink a[href*="/startseite/verein/"]'):
                cid = int(re.search(r"/verein/(\d+)", a["href"]).group(1))
                clubs[cid] = (a["href"].split("/")[1], a.get("title") or a.get_text(strip=True))
            log(f"{league} {season}: {len(clubs)} clubs")
            for cid, (cslug, cname) in clubs.items():
                html = fetch(f"{TM}/{cslug}/kader/verein/{cid}/saison_id/{season}/plus/1",
                             f"tm/squad/{cid}_{season}.html")
                if html:
                    rows += parse_squad(html, cid, cname, league, season)
    return pd.DataFrame(rows)


def parse_squad(html, club_id, club_name, league, season):
    out = []
    soup = BeautifulSoup(html, "lxml")
    for tr in soup.select("table.items > tbody > tr"):
        link = tr.select_one('td.hauptlink a[href*="/profil/spieler/"]')
        if not link:
            continue
        inline = tr.select("table.inline-table tr")
        sub_pos = inline[1].get_text(strip=True) if len(inline) > 1 else None
        dob = None
        for td in tr.find_all("td", recursive=False):
            m = re.match(r"(\d{2})/(\d{2})/(\d{4})", td.get_text(strip=True))
            if m:
                dob = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                break
        flags = [img["title"] for img in tr.select("img.flaggenrahmen")]
        img = tr.select_one("img.bilderrahmen-fixed")
        mv = tr.select_one("td.rechts.hauptlink")
        out.append({
            "player_id": int(re.search(r"/spieler/(\d+)", link["href"]).group(1)),
            "name": link.get_text(strip=True),
            "sub_position": sub_pos,
            "date_of_birth": dob,
            "country_of_citizenship": flags[0] if flags else None,
            "image_url": img.get("data-src") if img else None,
            "market_value": parse_money(mv.get_text(strip=True) if mv else None),
            "club_id": club_id, "club_name": club_name, "league": league, "season": season,
        })
    return out


def fetch_transfer_histories(player_ids):
    """Club moves from Transfermarkt's transfer-history endpoint, as dataset-shaped rows."""
    def one(pid):
        text = fetch(f"{TM}/ceapi/transferHistory/list/{pid}", f"tm/transfers/{pid}.json", min_delay=0.25)
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        rows = []
        for t in data.get("transfers", []):
            if t.get("upcoming") or t.get("futureTransfer"):
                continue
            ids = []
            for side in ("from", "to"):
                m = re.search(r"/verein/(\d+)", t[side].get("href") or "")
                ids.append(int(m.group(1)) if m else None)
            rows.append({"player_id": pid, "transfer_date": t.get("dateUnformatted"),
                         "from_club_id": ids[0], "to_club_id": ids[1],
                         "from_club_name": t["from"].get("clubName"), "to_club_name": t["to"].get("clubName"),
                         "market_value_in_eur": parse_money(t.get("marketValue"))})
        return rows

    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(one, player_ids):
            rows += r
            done += 1
            if done % 250 == 0:
                log(f"  transfer histories: {done}/{len(player_ids)}")
    return pd.DataFrame(rows)


def fetch_peak_values(player_ids):
    """Career-high market value from Transfermarkt's value graph (covers values from ~2004 on)."""
    def one(pid):
        text = fetch(f"{TM}/ceapi/marketValueDevelopment/graph/{pid}", f"tm/values/{pid}.json", min_delay=0.25)
        try:
            return pid, max((int(p["y"]) for p in json.loads(text or "{}").get("list", []) if p.get("y")), default=0)
        except (json.JSONDecodeError, ValueError, TypeError):
            return pid, 0

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(one, player_ids))


# --------------------------------------------------------------------------- building

def clean_club_name(name):
    name = re.sub(r"\b(Football Club|Futbol Club|Fußball-Club|S\.p\.A\.|S\.A\.D\.|SAD|e\.V\.|"
                  r"Limited|Ltd\.?|GmbH( & Co\. KGaA)?|KGaA|SASP|S\.A\.)", "", name or "")
    return re.sub(r"\s{2,}", " ", name).strip(" .,")


def build(skip_fetch=False):
    ds = download_dataset()
    players, apps, transfers, clubs = ds["players"], ds["appearances"], ds["transfers"], ds["clubs"]

    # --- universe: anyone who appeared in a top-5 league since 2012, or was in a top-5 squad in 2010-12
    top5_apps = apps[apps.competition_id.isin(TOP5)]
    early = scrape_early_squads() if not skip_fetch else pd.DataFrame(
        columns=["player_id", "name", "sub_position", "date_of_birth", "country_of_citizenship",
                 "image_url", "market_value", "club_id", "club_name", "league", "season"])
    universe = set(top5_apps.player_id) | set(early.player_id)
    log(f"universe: {len(universe)} players ({len(set(early.player_id) - set(top5_apps.player_id))} only pre-2012)")

    # --- club -> league. Prefer the league a club actually played league games in.
    league_apps = apps[apps.competition_id.isin(LEAGUE_NAMES)]
    club_league = (league_apps.groupby(["player_club_id", "competition_id"]).size()
                   .reset_index().sort_values(0).drop_duplicates("player_club_id", keep="last")
                   .set_index("player_club_id").competition_id.to_dict())
    for cid, lg in zip(clubs.club_id, clubs.domestic_competition_id):
        if lg in LEAGUE_NAMES:
            club_league.setdefault(cid, lg)
    for cid, lg in zip(early.club_id, early.league):
        club_league.setdefault(cid, lg)

    # --- club names: short names from transfer records beat clubs.csv's legal names
    club_name = {cid: clean_club_name(n) for cid, n in zip(clubs.club_id, clubs.name)}
    club_name.update(dict(zip(early.club_id, early.club_name)))

    # --- transfer histories: dataset first, endpoint for the rest
    tr = transfers[transfers.player_id.isin(universe)][
        ["player_id", "transfer_date", "from_club_id", "to_club_id", "from_club_name", "to_club_name", "market_value_in_eur"]]
    missing = sorted(universe - set(tr.player_id))
    if not skip_fetch:
        log(f"fetching transfer histories for {len(missing)} players")
        tr = pd.concat([tr, fetch_transfer_histories(missing)], ignore_index=True)
    # Transfermarkt uses 00 for an unknown day/month and 0000-00-00 for an unknown date; keep the move, drop the date.
    tr["transfer_date"] = tr.transfer_date.str.replace("-00", "-01").where(tr.transfer_date.str.match(r"(19|20)\d\d-", na=False))
    tr = tr[tr.transfer_date.isna() | (tr.transfer_date <= datetime.now().strftime("%Y-%m-%d"))]
    for col_id, col_name in (("from_club_id", "from_club_name"), ("to_club_id", "to_club_name")):
        short = tr.dropna(subset=[col_id]).groupby(col_id)[col_name].agg(lambda s: s.mode().iat[0])
        club_name.update({int(k): v for k, v in short.items()})

    # --- player -> clubs, with the date each stint was first seen
    stints = pd.concat([
        tr[["player_id", "to_club_id", "transfer_date"]].rename(columns={"to_club_id": "club_id", "transfer_date": "date"}),
        tr[["player_id", "from_club_id", "transfer_date"]].rename(columns={"from_club_id": "club_id", "transfer_date": "date"})
          .assign(date=lambda d: pd.to_datetime(d.date, errors="coerce") - pd.Timedelta(days=1)).assign(date=lambda d: d.date.dt.strftime("%Y-%m-%d")),
        apps[apps.player_id.isin(universe)][["player_id", "player_club_id", "date"]].rename(columns={"player_club_id": "club_id"}),
        early.assign(date=early.season.astype(str) + "-08-01")[["player_id", "club_id", "date"]],
    ], ignore_index=True).dropna(subset=["club_id"])
    stints["club_id"] = stints.club_id.astype(int)
    stints = stints[stints.player_id.isin(universe)]
    stints = stints[~stints.club_id.map(lambda c: bool(NOT_A_CLUB.search(club_name.get(c, "Unknown"))))]
    player_clubs = (stints.groupby(["player_id", "club_id"]).date.agg(["min", "max"]).reset_index()
                    .sort_values(["player_id", "min"]))

    # --- player profiles
    prof = players[players.player_id.isin(universe)].copy()
    prof["peak_value"] = prof.highest_market_value_in_eur
    early_prof = (early.sort_values("season").groupby("player_id")
                  .agg(name=("name", "last"), sub_position=("sub_position", "last"),
                       date_of_birth=("date_of_birth", "last"), country_of_citizenship=("country_of_citizenship", "last"),
                       image_url=("image_url", "last"), early_value=("market_value", "max")).reset_index())
    prof = prof.merge(early_prof[["player_id", "early_value"]], on="player_id", how="left")
    only_early = early_prof[~early_prof.player_id.isin(prof.player_id)]
    prof = pd.concat([prof, only_early], ignore_index=True)
    transfer_value = tr.groupby("player_id").market_value_in_eur.max().rename("transfer_value")
    prof = prof.merge(transfer_value, left_on="player_id", right_index=True, how="left")
    prof["peak_value"] = prof[["peak_value", "early_value", "transfer_value"]].max(axis=1)
    # Values in the dataset / 2010-12 squad pages undersell players who peaked before 2010 (Henry, Del Piero...).
    undervalued = prof[prof.player_id.isin(early.player_id) & ~(prof.peak_value >= 20_000_000)].player_id.tolist()
    if not skip_fetch and undervalued:
        log(f"fetching career-high values for {len(undervalued)} players")
        prof["peak_value"] = prof[["peak_value"]].assign(
            graph=prof.player_id.map(fetch_peak_values(undervalued))).max(axis=1)

    minutes = top5_apps.groupby("player_id").minutes_played.sum()
    last_top5 = pd.concat([top5_apps.assign(y=pd.to_datetime(top5_apps.date).dt.year)[["player_id", "y"]],
                           early.assign(y=early.season + 1)[["player_id", "y"]]]).groupby("player_id").y.max()
    early_seasons = early.groupby("player_id").season.nunique()

    out = []
    for p in prof.itertuples():
        sub = p.sub_position if isinstance(p.sub_position, str) and p.sub_position in BROAD_POSITION else None
        if not sub or not isinstance(p.name, str):
            continue
        nation, flag, continent = lookup(p.country_of_citizenship if isinstance(p.country_of_citizenship, str) else None)
        dob = str(p.date_of_birth)[:10] if isinstance(p.date_of_birth, str) else None
        mins = int(minutes.get(p.player_id, 0))
        value = int(p.peak_value) if pd.notna(p.peak_value) else 0
        # Mystery players should be recognisable: a big peak value and real top-5 minutes
        # (or both 2010-12 seasons in a top-5 squad, since minutes only exist from 2012 on).
        famous = value >= 20_000_000 and (mins >= 4_000 or early_seasons.get(p.player_id, 0) >= 2)
        out.append({
            "id": int(p.player_id), "name": p.name.strip(), "nationality": nation, "flag": flag,
            "continent": continent, "position": BROAD_POSITION[sub], "sub_position": sub,
            "birth_date": dob, "image_url": p.image_url if isinstance(p.image_url, str) else None,
            "peak_value_eur": value, "top5_minutes": mins, "last_top5_year": int(last_top5.get(p.player_id, 0)) or None,
            "mystery_eligible": famous,
        })
    players_out = pd.DataFrame(out)
    player_clubs = player_clubs[player_clubs.player_id.isin(players_out.id)]
    used_clubs = sorted(set(player_clubs.club_id))
    clubs_out = pd.DataFrame({"id": used_clubs,
                              "name": [club_name.get(c, f"Club {c}") for c in used_clubs],
                              "league_id": [club_league.get(c) for c in used_clubs]})
    log(f"players: {len(players_out)} ({players_out.mystery_eligible.sum()} mystery-eligible), "
        f"clubs: {len(clubs_out)}, player_clubs: {len(player_clubs)}")
    return players_out, clubs_out, player_clubs


# --------------------------------------------------------------------------- loading

def load(players_out, clubs_out, player_clubs):
    schema = (ROOT.parent / "db" / "schema.sql").read_text()
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(schema)
        with cur.copy("COPY leagues (id, name) FROM STDIN") as cp:
            for k, v in LEAGUE_NAMES.items():
                cp.write_row((k, v))
        with cur.copy("COPY clubs (id, name, league_id) FROM STDIN") as cp:
            for r in clubs_out.itertuples(index=False):
                cp.write_row((r.id, r.name, r.league_id if isinstance(r.league_id, str) else None))
        cols = ["id", "name", "nationality", "flag", "continent", "position", "sub_position", "birth_date",
                "image_url", "peak_value_eur", "top5_minutes", "last_top5_year", "mystery_eligible"]
        with cur.copy(f"COPY players ({', '.join(cols)}) FROM STDIN") as cp:
            for r in players_out[cols].itertuples(index=False):
                cp.write_row([None if (isinstance(v, float) and pd.isna(v)) else v for v in r])
        with cur.copy("COPY player_clubs (player_id, club_id, first_seen, last_seen) FROM STDIN") as cp:
            for r in player_clubs.itertuples(index=False):
                cp.write_row((int(r.player_id), int(r.club_id), *(d if isinstance(d, str) else None for d in r[2:4])))
        cur.execute("UPDATE players SET search_name = lower(unaccent(name))")
        cur.execute("ANALYZE")
    log(f"loaded into {DATABASE_URL.rsplit('@', 1)[-1]}")


if __name__ == "__main__":
    load(*build(skip_fetch="--skip-fetch" in sys.argv))
