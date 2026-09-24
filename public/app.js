const MAX_GUESSES = 5;
const FLIP_MS = 300; // stagger between tiles
const COLUMNS = ["nation", "position", "leagues", "clubs", "born"];

const $ = (sel) => document.querySelector(sel);
const board = $("#board");
const input = $("#guess-input");
const list = $("#suggestions");

let game = null; // { id, rows: [statuses[]], over, animating }
let suggestions = [];
let active = -1;

// ---------------------------------------------------------------- api

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

// ---------------------------------------------------------------- board

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function renderEmptyBoard() {
  board.replaceChildren();
  for (let i = 0; i < MAX_GUESSES; i++) {
    const row = el("div", "row");
    row.append(el("div", "row-name"));
    const tiles = el("div", "tiles");
    for (let j = 0; j < COLUMNS.length; j++) tiles.append(el("div", "tile"));
    row.append(tiles, el("div", "chips"));
    board.append(row);
  }
}

function fillTile(tile, key, attr) {
  tile.replaceChildren();
  tile.title = "";
  switch (key) {
    case "nation":
      tile.append(el("div", "flag", attr.flag || "🏳️"), el("div", "small wrap", attr.label));
      tile.title = `${attr.label} (${attr.continent})`;
      break;
    case "position":
      tile.append(el("div", "big", attr.label));
      tile.title = attr.full;
      break;
    case "leagues":
    case "clubs": {
      // Counts only; which ones are shared is spelled out in the lists under the row.
      const shared = attr.items.filter((x) => x.shared).length;
      tile.append(el("div", "big", `${shared}/${attr.items.length}`), el("div", "small", "shared"));
      tile.title = attr.items.map((x) => `${x.shared ? "✓" : "✗"} ${x.name}`).join("\n");
      break;
    }
    case "born":
      tile.append(el("div", "big", String(attr.label)));
      if (attr.direction) tile.append(el("div", "arrow", attr.direction === "up" ? "↑" : "↓"));
      tile.title = attr.direction === "up" ? "Mystery player was born later"
        : attr.direction === "down" ? "Mystery player was born earlier" : "";
      break;
  }
}

function revealRow(index, result) {
  const row = board.children[index];
  const tiles = row.querySelectorAll(".tile");
  row.querySelector(".row-name").textContent = result.player.name;

  const statuses = COLUMNS.map((k) => result[k].status);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const stagger = reduced ? 0 : FLIP_MS;

  COLUMNS.forEach((key, i) => {
    const tile = tiles[i];
    setTimeout(() => {
      tile.classList.add("flip");
      // Swap in the content at the midpoint of the flip, when the tile is edge-on.
      setTimeout(() => {
        fillTile(tile, key, result[key]);
        tile.classList.add(result[key].status);
      }, reduced ? 0 : 250);
    }, i * stagger);
  });

  return new Promise((resolve) => {
    setTimeout(() => {
      const details = row.querySelector(".chips");
      for (const [label, items] of [["Leagues", result.leagues.items], ["Clubs", result.clubs.items]]) {
        const line = el("div", "chip-line");
        const chips = el("div", "chip-list");
        for (const x of items) chips.append(el("span", "chip" + (x.shared ? " shared" : ""), x.name));
        if (!items.length) chips.append(el("span", "chip", "Unknown"));
        line.append(el("span", "chip-label", label), chips);
        details.append(line);
      }
      if (result.correct) row.classList.add("correct");
      resolve(statuses);
    }, COLUMNS.length * stagger + (reduced ? 0 : 300));
  });
}

// ---------------------------------------------------------------- game flow

async function newGame() {
  closeSuggestions();
  input.value = "";
  renderEmptyBoard();
  try {
    const { id } = await api("/api/games", {});
    game = { id, rows: [], over: false, animating: false };
    setInputEnabled(true);
    updateMeta();
    input.focus();
  } catch (e) {
    toast(e.message);
  }
}

async function submitGuess(player) {
  if (!game || game.over || game.animating) return;
  closeSuggestions();
  input.value = "";
  game.animating = true;
  setInputEnabled(false);
  try {
    const data = await api("/api/guess", { gameId: game.id, playerId: player.id });
    const statuses = await revealRow(game.rows.length, data.result);
    game.rows.push(statuses);
    game.over = data.over;
    updateMeta();
    if (data.over) finish(data.won, data.answer);
  } catch (e) {
    toast(e.message);
  } finally {
    game.animating = false;
    if (!game.over) {
      setInputEnabled(true);
      input.focus();
    }
  }
}

function finish(won, answer) {
  game.over = true;
  setInputEnabled(false);
  recordStats(won);
  setTimeout(() => showResult(won, answer), won ? 600 : 300);
}

function updateMeta() {
  const left = MAX_GUESSES - (game?.rows.length ?? 0);
  $("#guesses-left").textContent = game?.over ? "Game over" : `${left} guess${left === 1 ? "" : "es"} left`;
  $("#give-up-wrap").hidden = !!game?.over;
}

function setInputEnabled(on) {
  input.disabled = !on;
}

// ---------------------------------------------------------------- result + stats

function showResult(won, answer) {
  const tries = game.rows.length;
  $("#result-title").textContent = won
    ? ["Genius!", "Magnificent!", "Impressive!", "Splendid!", "Phew!"][tries - 1] || "Nice!"
    : "The mystery player was";
  const img = $("#answer-img");
  img.hidden = !answer.image_url;
  img.onerror = () => (img.hidden = true);
  img.src = answer.image_url || "";
  $("#answer-name").textContent = `${answer.flag || ""} ${answer.name}`.trim();
  $("#answer-meta").textContent = [answer.nationality, answer.position, answer.birth_year && `b. ${answer.birth_year}`]
    .filter(Boolean).join(" · ");
  $("#answer-clubs").textContent = answer.clubs.join(" → ");

  const s = loadStats();
  const stats = $("#stats");
  stats.replaceChildren();
  for (const [value, label] of [[s.played, "Played"], [s.played ? Math.round((100 * s.won) / s.played) : 0, "Win %"],
    [s.streak, "Streak"], [s.best, "Best"]]) {
    const d = el("div");
    d.append(el("b", "", String(value)), el("span", "", label));
    stats.append(d);
  }
  $("#share-btn").onclick = () => share(won);
  $("#result").showModal();
}

function share(won) {
  const emoji = { hit: "🟩", near: "🟨", miss: "⬛" };
  const text = [`Soccerdle ${won ? game.rows.length : "X"}/${MAX_GUESSES}`, "",
    ...game.rows.map((r) => r.map((s) => emoji[s]).join(""))].join("\n");
  navigator.clipboard?.writeText(text).then(() => toast("Copied to clipboard"), () => toast("Couldn't copy"));
}

function loadStats() {
  try {
    return { played: 0, won: 0, streak: 0, best: 0, ...JSON.parse(localStorage.getItem("soccerdle-stats") || "{}") };
  } catch {
    return { played: 0, won: 0, streak: 0, best: 0 };
  }
}

function recordStats(won) {
  const s = loadStats();
  s.played++;
  if (won) {
    s.won++;
    s.streak++;
    s.best = Math.max(s.best, s.streak);
  } else {
    s.streak = 0;
  }
  try {
    localStorage.setItem("soccerdle-stats", JSON.stringify(s));
  } catch { /* storage unavailable; stats just won't persist */ }
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 1800);
}

// ---------------------------------------------------------------- autocomplete

let searchTimer;
let searchSeq = 0;

input.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = input.value.trim();
  if (q.length < 2) return closeSuggestions();
  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq;
    try {
      const rows = await api(`/api/search?q=${encodeURIComponent(q)}`);
      if (seq === searchSeq) showSuggestions(rows);
    } catch (e) {
      toast(e.message);
    }
  }, 120);
});

function showSuggestions(rows) {
  suggestions = rows;
  active = rows.length ? 0 : -1;
  list.replaceChildren();
  if (!rows.length) {
    list.append(el("li", "empty", "No players found"));
  }
  rows.forEach((p, i) => {
    const li = el("li");
    li.setAttribute("role", "option");
    li.append(el("div", "s-name", p.name),
      el("div", "s-meta", [p.flag, p.sub_position, p.club, p.birth_year].filter(Boolean).join(" · ")));
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      submitGuess(suggestions[i]);
    });
    list.append(li);
  });
  list.hidden = false;
  highlight();
}

function highlight() {
  [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
  list.children[active]?.scrollIntoView({ block: "nearest" });
}

function closeSuggestions() {
  list.hidden = true;
  suggestions = [];
  active = -1;
}

input.addEventListener("keydown", (e) => {
  if (list.hidden || !suggestions.length) return;
  if (e.key === "ArrowDown") active = (active + 1) % suggestions.length;
  else if (e.key === "ArrowUp") active = (active - 1 + suggestions.length) % suggestions.length;
  else if (e.key === "Enter") return submitGuess(suggestions[active]);
  else if (e.key === "Escape") return closeSuggestions();
  else return;
  e.preventDefault();
  highlight();
});

input.addEventListener("blur", () => setTimeout(closeSuggestions, 100));

// ---------------------------------------------------------------- wiring

$("#new-btn").addEventListener("click", newGame);
$("#again-btn").addEventListener("click", () => {
  $("#result").close();
  newGame();
});
$("#help-btn").addEventListener("click", () => $("#help").showModal());
$("#give-up").addEventListener("click", async () => {
  if (!game || game.over || game.animating) return;
  try {
    const { answer } = await api("/api/give-up", { gameId: game.id });
    finish(false, answer);
    updateMeta();
  } catch (e) {
    toast(e.message);
  }
});
for (const d of document.querySelectorAll("dialog")) {
  d.querySelector(".close").addEventListener("click", () => d.close());
  d.addEventListener("click", (e) => e.target === d && d.close()); // backdrop click
}

try {
  if (!localStorage.getItem("soccerdle-seen-help")) {
    localStorage.setItem("soccerdle-seen-help", "1");
    $("#help").showModal();
  }
} catch { /* ignore */ }

newGame();
