// Soccerdle server: static files + a tiny JSON API over Postgres. No framework, one dependency (pg).
import http from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { randomUUID } from "node:crypto";
import pg from "pg";

const PORT = Number(process.env.PORT) || 3000;
const MAX_GUESSES = 5;
const PUBLIC_DIR = join(import.meta.dirname, "..", "public");
const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://wordle:wordle@localhost:5433/soccerdle",
});

// ---------------------------------------------------------------- data access

const PLAYER_SQL = `
  SELECT p.id, p.name, p.nationality, p.flag, p.continent, p.position, p.sub_position,
         extract(year FROM p.birth_date)::int AS birth_year, p.image_url,
         coalesce(json_agg(json_build_object('id', c.id, 'name', c.name, 'league', c.league_id)
                  ORDER BY pc.first_seen) FILTER (WHERE c.id IS NOT NULL), '[]') AS clubs
  FROM players p
  LEFT JOIN player_clubs pc ON pc.player_id = p.id
  LEFT JOIN clubs c ON c.id = pc.club_id
  WHERE p.id = $1
  GROUP BY p.id`;

async function getPlayer(id) {
  const { rows } = await pool.query(PLAYER_SQL, [id]);
  if (!rows[0]) return null;
  const leagueIds = [...new Set(rows[0].clubs.map((c) => c.league).filter(Boolean))];
  const { rows: leagues } = await pool.query("SELECT id, name FROM leagues WHERE id = ANY($1)", [leagueIds]);
  return { ...rows[0], leagues: leagues.map((l) => ({ id: l.id, name: l.name, short: LEAGUE_SHORT[l.id] || l.name })) };
}

async function searchPlayers(q) {
  const { rows } = await pool.query(
    `WITH q AS (SELECT lower(unaccent($1)) AS t)
     SELECT p.id, p.name, p.flag, p.sub_position, extract(year FROM p.birth_date)::int AS birth_year,
            (SELECT c.name FROM player_clubs pc JOIN clubs c ON c.id = pc.club_id
              WHERE pc.player_id = p.id ORDER BY pc.last_seen DESC LIMIT 1) AS club
     FROM players p, q
     WHERE p.search_name LIKE '%' || q.t || '%'
     ORDER BY (p.search_name LIKE q.t || '%' OR p.search_name LIKE '% ' || q.t || '%') DESC,
              p.peak_value_eur DESC
     LIMIT 8`,
    [q],
  );
  return rows;
}

async function randomMysteryId() {
  const { rows } = await pool.query("SELECT id FROM players WHERE mystery_eligible ORDER BY random() LIMIT 1");
  return rows[0].id;
}

// ---------------------------------------------------------------- game logic

const LEAGUE_SHORT = {
  GB1: "EPL", ES1: "LaLiga", IT1: "Serie A", L1: "BuLi", FR1: "Ligue 1", MLS1: "MLS", SA1: "Saudi",
  NL1: "NED", PO1: "POR", TR1: "TUR", SC1: "SCO", BE1: "BEL", RU1: "RUS", UKR1: "UKR", GR1: "GRE",
  DK1: "DEN", A1: "AUT", C1: "SUI", KR1: "CRO", TS1: "CZE", PL1: "POL", RO1: "ROU", SER1: "SRB",
  SE1: "SWE", NO1: "NOR", BRA1: "BRA", ARG1: "ARG", MEX1: "MEX", JAP1: "JPN", RSK1: "KOR", AUS1: "AUS",
};

const POS_SHORT = {
  Goalkeeper: "GK", "Centre-Back": "CB", "Left-Back": "LB", "Right-Back": "RB",
  "Defensive Midfield": "DM", "Central Midfield": "CM", "Attacking Midfield": "AM",
  "Left Midfield": "LM", "Right Midfield": "RM", "Left Winger": "LW", "Right Winger": "RW",
  "Centre-Forward": "CF", "Second Striker": "SS",
};

// Each attribute gets a status: "hit" (green), "near" (yellow) or "miss" (grey).
function compare(guess, mystery) {
  const mysteryClubs = new Set(mystery.clubs.map((c) => c.id));
  const mysteryLeagues = new Set(mystery.leagues.map((l) => l.id));
  const sharedLeagues = guess.leagues.filter((l) => mysteryLeagues.has(l.id));
  const sharedClubs = guess.clubs.filter((c) => mysteryClubs.has(c.id));
  const correct = guess.id === mystery.id;
  const yearDiff = (mystery.birth_year ?? 0) - (guess.birth_year ?? 0);

  return {
    correct,
    player: { id: guess.id, name: guess.name },
    nation: {
      status: guess.nationality === mystery.nationality ? "hit" : guess.continent === mystery.continent ? "near" : "miss",
      flag: guess.flag, label: guess.nationality, continent: guess.continent,
    },
    position: {
      status: guess.sub_position === mystery.sub_position ? "hit" : guess.position === mystery.position ? "near" : "miss",
      label: POS_SHORT[guess.sub_position] || guess.sub_position, full: guess.sub_position,
    },
    leagues: {
      status: sharedLeagues.length === 0 ? "miss"
        : sharedLeagues.length === guess.leagues.length && guess.leagues.length === mysteryLeagues.size ? "hit" : "near",
      // Shared leagues first, so they're visible even when the tile truncates the list.
      items: guess.leagues
        .map((l) => ({ label: l.short, name: l.name, shared: mysteryLeagues.has(l.id) }))
        .sort((a, b) => b.shared - a.shared),
    },
    clubs: {
      status: correct ? "hit" : sharedClubs.length ? "near" : "miss",
      shared: sharedClubs.length,
      items: guess.clubs.map((c) => ({ name: c.name, shared: mysteryClubs.has(c.id) })),
    },
    born: {
      status: yearDiff === 0 ? "hit" : Math.abs(yearDiff) <= 2 ? "near" : "miss",
      label: guess.birth_year ?? "?",
      direction: yearDiff > 0 ? "up" : yearDiff < 0 ? "down" : null, // up = mystery born later
    },
  };
}

function reveal(p) {
  return {
    name: p.name, flag: p.flag, nationality: p.nationality, position: p.sub_position,
    birth_year: p.birth_year, image_url: p.image_url, clubs: p.clubs.map((c) => c.name),
  };
}

// In-memory games; a prototype doesn't need persistence across restarts.
const games = new Map();
setInterval(() => {
  const cutoff = Date.now() - 24 * 3600e3;
  for (const [id, g] of games) if (g.created < cutoff) games.delete(id);
}, 3600e3).unref();

// ---------------------------------------------------------------- http

const routes = {
  "GET /api/search": async (req, url) => {
    const q = (url.searchParams.get("q") || "").trim();
    return q.length < 2 ? [] : searchPlayers(q.slice(0, 50));
  },
  "POST /api/games": async () => {
    const id = randomUUID();
    games.set(id, { mysteryId: await randomMysteryId(), guesses: [], over: false, created: Date.now() });
    return { id, maxGuesses: MAX_GUESSES };
  },
  "POST /api/guess": async (req) => {
    const body = await readJson(req);
    const playerId = Number(body.playerId);
    const game = games.get(body.gameId);
    if (!game) throw httpError(404, "Game not found — start a new one.");
    if (game.over) throw httpError(400, "This game is over.");
    if (game.guesses.includes(playerId)) throw httpError(400, "You already guessed that player.");
    const [guess, mystery] = await Promise.all([getPlayer(playerId), getPlayer(game.mysteryId)]);
    if (!guess) throw httpError(400, "Unknown player.");

    game.guesses.push(guess.id);
    const result = compare(guess, mystery);
    game.over = result.correct || game.guesses.length >= MAX_GUESSES;
    return {
      result,
      guessesLeft: MAX_GUESSES - game.guesses.length,
      over: game.over,
      won: result.correct,
      answer: game.over ? reveal(mystery) : undefined,
    };
  },
  "POST /api/give-up": async (req) => {
    const game = games.get((await readJson(req)).gameId);
    if (!game) throw httpError(404, "Game not found.");
    game.over = true;
    return { answer: reveal(await getPlayer(game.mysteryId)) };
  },
};

const MIME = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".ico": "image/x-icon" };

async function serveStatic(res, pathname) {
  const file = normalize(join(PUBLIC_DIR, pathname === "/" ? "index.html" : pathname));
  if (!file.startsWith(PUBLIC_DIR)) return send(res, 403, "Forbidden");
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": (MIME[extname(file)] || "application/octet-stream") + "; charset=utf-8" });
    res.end(body);
  } catch {
    send(res, 404, "Not found");
  }
}

function send(res, status, body) {
  const json = typeof body !== "string";
  res.writeHead(status, { "Content-Type": json ? "application/json" : "text/plain" });
  res.end(json ? JSON.stringify(body) : body);
}

function httpError(status, message) {
  return Object.assign(new Error(message), { status });
}

async function readJson(req) {
  let data = "";
  for await (const chunk of req) {
    data += chunk;
    if (data.length > 10_000) throw httpError(413, "Body too large");
  }
  try {
    return JSON.parse(data || "{}");
  } catch {
    throw httpError(400, "Invalid JSON");
  }
}

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const handler = routes[`${req.method} ${url.pathname}`];
    if (!handler) return req.method === "GET" ? serveStatic(res, url.pathname) : send(res, 404, { error: "Not found" });
    try {
      send(res, 200, await handler(req, url));
    } catch (err) {
      if (!err.status) console.error(err);
      send(res, err.status || 500, { error: err.status ? err.message : "Server error" });
    }
  })
  .listen(PORT, () => console.log(`Soccerdle running at http://localhost:${PORT}`));
