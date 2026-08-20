

/* ---------- team info ---------- */
var teams = {
  bolts:   { name: "Lightning",     city: "Tampa Bay", abbr: "TBL", color: "#3b82f6", record: "31-18-5" },
  oilers:  { name: "Oilers",        city: "Edmonton",  abbr: "EDM", color: "#f97316", record: "34-16-4" },
  avs:     { name: "Avalanche",     city: "Colorado",  abbr: "COL", color: "#7c3aed", record: "36-14-3" },
  panthers:{ name: "Panthers",      city: "Florida",   abbr: "FLA", color: "#ef4444", record: "33-17-4" },
  bruins:  { name: "Bruins",        city: "Boston",    abbr: "BOS", color: "#eab308", record: "29-19-6" },
  rangers: { name: "Rangers",       city: "New York",  abbr: "NYR", color: "#2563eb", record: "32-17-4" },
  knights: { name: "Golden Knights",city: "Vegas",     abbr: "VGK", color: "#d4af37", record: "30-18-5" },
  stars:   { name: "Stars",         city: "Dallas",    abbr: "DAL", color: "#16a34a", record: "35-15-3" }
};

/* default stats helper so we don't repeat ourselves */
function makeStats(extra) {
  var base = {
    goalsFor: 3.2, goalsAgainst: 2.8, powerPlay: 22,
    penaltyKill: 80, shotsPerGame: 31, faceoffWin: 50,
    form: ["W", "W", "L", "W", "O"]
  };
  for (var key in extra) {
    base[key] = extra[key];
  }
  return base;
}

/* ---------- upcoming games ---------- */
var upcomingGames = [
  {
    id: "g1", time: "Sat 7:00 PM",
    home: teams.bolts, away: teams.panthers,
    homeWinProb: 48, confidence: 72, homeOdds: 118, awayOdds: -135,
    homeStats: makeStats({ goalsFor: 3.3, goalsAgainst: 2.9, powerPlay: 24, penaltyKill: 79, shotsPerGame: 32, faceoffWin: 51, form: ["W","L","W","W","L"] }),
    awayStats: makeStats({ goalsFor: 3.5, goalsAgainst: 2.6, powerPlay: 26, penaltyKill: 83, shotsPerGame: 33, faceoffWin: 53, form: ["W","W","W","O","W"] })
  },
  {
    id: "g2", time: "Sat 9:30 PM",
    home: teams.rangers, away: teams.bruins,
    homeWinProb: 58, confidence: 65, homeOdds: -140, awayOdds: 122,
    homeStats: makeStats({ goalsFor: 3.1, goalsAgainst: 2.5, powerPlay: 23, penaltyKill: 84, shotsPerGame: 30, faceoffWin: 49, form: ["W","W","L","W","W"] }),
    awayStats: makeStats({ goalsFor: 2.9, goalsAgainst: 2.8, powerPlay: 20, penaltyKill: 81, shotsPerGame: 29, faceoffWin: 52, form: ["L","W","O","L","W"] })
  },
  {
    id: "g3", time: "Sat 10:00 PM",
    home: teams.knights, away: teams.stars,
    homeWinProb: 44, confidence: 81, homeOdds: 134, awayOdds: -155,
    homeStats: makeStats({ goalsFor: 3.0, goalsAgainst: 2.9, powerPlay: 21, penaltyKill: 78, shotsPerGame: 31, faceoffWin: 48, form: ["L","W","L","O","W"] }),
    awayStats: makeStats({ goalsFor: 3.6, goalsAgainst: 2.4, powerPlay: 27, penaltyKill: 85, shotsPerGame: 34, faceoffWin: 55, form: ["W","W","W","W","L"] })
  },
  {
    id: "g4", time: "Sat 11:00 PM",
    home: teams.avs, away: teams.bolts,
    homeWinProb: 63, confidence: 69, homeOdds: -165, awayOdds: 142,
    homeStats: makeStats({ goalsFor: 3.7, goalsAgainst: 2.5, powerPlay: 28, penaltyKill: 82, shotsPerGame: 35, faceoffWin: 54, form: ["W","W","O","W","W"] }),
    awayStats: makeStats({ goalsFor: 3.3, goalsAgainst: 2.9, powerPlay: 24, penaltyKill: 79, shotsPerGame: 32, faceoffWin: 51, form: ["W","L","W","W","L"] })
  }
];

/* ---------- live game timeline ---------- */
var liveTimeline = [
  { minute: 0,  label: "Puck drop",            homeProb: 54 },
  { minute: 6,  label: "EDM goal — McDavid",   homeProb: 63 },
  { minute: 13, label: "COL power play",       homeProb: 55 },
  { minute: 18, label: "COL goal — MacKinnon", homeProb: 47 },
  { minute: 24, label: "EDM goal — Draisaitl", homeProb: 60 },
  { minute: 31, label: "EDM penalty kill",     homeProb: 58 },
  { minute: 38, label: "EDM hits crossbar",    homeProb: 61 }
];

/* ---------- comments ---------- */
var comments = [
  { user: "SlapshotSam",      hue: 120, time: "12m", text: "Panthers PK has been elite lately. Taking the road dog with confidence here.", likes: 34, pick: "away" },
  { user: "IceColdAnalytics", hue: 200, time: "27m", text: "Model loves Tampa at home but their goaltending splits worry me. Live betting only.", likes: 21, pick: "home" },
  { user: "PuckLuck99",       hue: 280, time: "44m", text: "Back-to-back for Florida, fatigue is real. Lightning steal this one in OT.", likes: 12, pick: "home" },
  { user: "BlueLineBetty",    hue: 40,  time: "1h",  text: "Faceoff win % gap is the tell. Cats control possession and grind it out.", likes: 47, pick: "away" }
];

/* ---------- leaderboard ---------- */
var leaderboard = [
  { rank: 1, user: "FrozenOracle",     hue: 190, accuracy: 74.2, streak: 9, points: 12840, trend: "up" },
  { rank: 2, user: "TwineTimeTom",     hue: 90,  accuracy: 71.8, streak: 5, points: 11990, trend: "up" },
  { rank: 3, user: "IceColdAnalytics", hue: 200, accuracy: 70.1, streak: 2, points: 11420, trend: "flat" },
  { rank: 4, user: "BlueLineBetty",    hue: 40,  accuracy: 68.9, streak: 4, points: 10870, trend: "up" },
  { rank: 5, user: "SlapshotSam",      hue: 120, accuracy: 67.3, streak: 0, points: 10210, trend: "down" },
  { rank: 6, user: "PuckLuck99",       hue: 280, accuracy: 65.0, streak: 1, points: 9680,  trend: "flat" }
];

/* the stat rows shown in the matchup comparison */
var statRows = [
  { key: "goalsFor",     label: "Goals / game",  max: 5 },
  { key: "goalsAgainst", label: "Goals against", max: 5 },
  { key: "powerPlay",    label: "Power play",    max: 35, suffix: "%" },
  { key: "penaltyKill",  label: "Penalty kill",  max: 100, suffix: "%" },
  { key: "shotsPerGame", label: "Shots / game",  max: 40 },
  { key: "faceoffWin",   label: "Faceoff win",   max: 65, suffix: "%" }
];


/* ===========================================================
   small helper functions
   =========================================================== */
function formatOdds(o) {
  return o > 0 ? "+" + o : "" + o;
}

/* make the two letters for an avatar from a username */
function initials(name) {
  return name.slice(0, 2).toUpperCase();
}


/* ===========================================================
   1) MOBILE MENU
   =========================================================== */
var menuBtn = document.getElementById("menuBtn");
var navLinks = document.getElementById("navLinks");

menuBtn.onclick = function () {
  navLinks.classList.toggle("open");
};

/* close the menu after clicking a link */
var links = navLinks.getElementsByTagName("a");
for (var i = 0; i < links.length; i++) {
  links[i].onclick = function () {
    navLinks.classList.remove("open");
  };
}


/* ===========================================================
   2) UPCOMING GAME CARDS
   =========================================================== */
function buildFormPips(form) {
  var html = '<div class="form-pips">';
  for (var i = 0; i < form.length; i++) {
    html += '<span class="pip ' + form[i] + '">' + form[i] + "</span>";
  }
  return html + "</div>";
}

function buildTeamSide(team, odds, isFav) {
  return (
    '<div class="team-side ' + (isFav ? "fav" : "") + '">' +
      '<span class="team-logo" style="--c:' + team.color + '">' + team.abbr + "</span>" +
      '<div class="team-side-info">' +
        '<div class="team-name-row">' +
          '<span class="bold">' + team.name + "</span>" +
          (isFav ? '<span class="fav-tag">Fav</span>' : "") +
        "</div>" +
        '<div class="team-meta">' +
          '<span class="muted tiny">' + team.record + "</span>" +
          buildFormPips(team.formForCard) +
        "</div>" +
      "</div>" +
      '<span class="odds">' + formatOdds(odds) + "</span>" +
    "</div>"
  );
}

function buildGameCard(game) {
  var homeFav = game.homeWinProb >= 50;
  var favTeam = homeFav ? game.home : game.away;
  var edge = homeFav ? game.homeWinProb : 100 - game.homeWinProb;

  /* attach the form arrays so buildTeamSide can read them */
  game.home.formForCard = game.homeStats.form;
  game.away.formForCard = game.awayStats.form;

  return (
    '<article class="pred-card glass">' +
      '<div class="pred-top">' +
        "<span>🕒 " + game.time + "</span>" +
        '<span class="edge-pill">📈 Model edge ' + edge + "%</span>" +
      "</div>" +
      '<div class="pred-teams">' +
        '<div class="pred-sides">' +
          buildTeamSide(game.home, game.homeOdds, favTeam === game.home) +
          buildTeamSide(game.away, game.awayOdds, favTeam === game.away) +
        "</div>" +
        '<div class="mini-ring">' + buildConfRing(game.confidence, 60) + "</div>" +
      "</div>" +
      buildProbBar(game.home, game.away, game.homeWinProb) +
      '<div class="pred-foot">' +
        '<span class="muted tiny">Pick: <span class="bold" style="color:var(--foreground)">' +
          favTeam.city + " " + favTeam.name + "</span></span>" +
        '<a href="#discussion" class="btn btn-secondary btn-sm">💬 Discuss</a>' +
      "</div>" +
    "</article>"
  );
}

/* a simple win-probability bar (used in cards) */
function buildProbBar(home, away, homeProb) {
  var awayProb = 100 - homeProb;
  return (
    '<div class="prob-block" style="margin-top:0">' +
      '<div class="prob-labels">' +
        '<div class="prob-side"><span class="dot" style="background:' + home.color + '"></span>' +
          '<span class="bold">' + home.abbr + '</span><span class="mono bold">' + homeProb + "%</span></div>" +
        '<div class="prob-side"><span class="mono bold">' + awayProb + "%</span>" +
          '<span class="bold">' + away.abbr + '</span><span class="dot" style="background:' + away.color + '"></span></div>' +
      "</div>" +
      '<div class="prob-bar">' +
        '<div class="prob-fill-home" style="width:' + homeProb + "%;background:linear-gradient(90deg," + home.color + ",#fff)\"></div>" +
        '<div class="prob-fill-away" style="width:' + awayProb + "%;background:linear-gradient(270deg," + away.color + ",#fff)\"></div>" +
        '<div class="prob-mid"></div>' +
      "</div>" +
    "</div>"
  );
}

/* a small SVG confidence ring */
function buildConfRing(value, size) {
  var stroke = size > 100 ? 12 : 6;
  var r = (size - stroke) / 2;
  var c = 2 * Math.PI * r;
  var offset = c - (value / 100) * c;
  var color = value >= 75 ? "var(--green)" : value >= 60 ? "var(--primary)" : "var(--gold)";

  return (
    '<svg width="' + size + '" height="' + size + '" style="transform:rotate(-90deg)">' +
      '<circle cx="' + size/2 + '" cy="' + size/2 + '" r="' + r + '" fill="none" stroke="var(--secondary)" stroke-width="' + stroke + '"/>' +
      '<circle cx="' + size/2 + '" cy="' + size/2 + '" r="' + r + '" fill="none" stroke="' + color +
        '" stroke-width="' + stroke + '" stroke-linecap="round" stroke-dasharray="' + c +
        '" stroke-dashoffset="' + offset + '"/>' +
    "</svg>" +
    (size <= 60
      ? '<div style="text-align:center;margin-top:-' + (size/2 + 8) + 'px;margin-bottom:' + (size/2 - 8) +
        'px"><span class="mono bold" style="color:' + color + '">' + value + "</span></div>"
      : "")
  );
}

/* show a loading skeleton first, then the real cards (like fetching from an API) */
var gamesGrid = document.getElementById("gamesGrid");

function showSkeletons() {
  var html = "";
  for (var i = 0; i < 4; i++) {
    html +=
      '<div class="pred-card glass" style="opacity:.5">' +
        '<div style="height:14px;width:120px;background:var(--secondary);border-radius:4px;margin-bottom:16px"></div>' +
        '<div style="height:48px;background:var(--secondary);border-radius:12px;margin-bottom:12px"></div>' +
        '<div style="height:48px;background:var(--secondary);border-radius:12px"></div>' +
      "</div>";
  }
  gamesGrid.innerHTML = html;
}

function showGameCards() {
  var html = "";
  for (var i = 0; i < upcomingGames.length; i++) {
    html += buildGameCard(upcomingGames[i]);
  }
  gamesGrid.innerHTML = html;
}

showSkeletons();
setTimeout(showGameCards, 1000); /* small delay so it feels like loading data */


/* ===========================================================
   3) MATCHUP COMPARISON
   =========================================================== */
var activeGameId = upcomingGames[2].id; /* start on the 3rd game like the original */
var matchupTabs = document.getElementById("matchupTabs");

/* build the little tab buttons */
function buildMatchupTabs() {
  var html = "";
  for (var i = 0; i < upcomingGames.length; i++) {
    var g = upcomingGames[i];
    var active = g.id === activeGameId ? "active" : "";
    html += '<button class="' + active + '" data-id="' + g.id + '">' +
      g.home.abbr + " v " + g.away.abbr + "</button>";
  }
  matchupTabs.innerHTML = html;

  /* hook up the clicks */
  var btns = matchupTabs.getElementsByTagName("button");
  for (var j = 0; j < btns.length; j++) {
    btns[j].onclick = function () {
      activeGameId = this.getAttribute("data-id");
      buildMatchupTabs();
      showMatchup();
    };
  }
}

function findGame(id) {
  for (var i = 0; i < upcomingGames.length; i++) {
    if (upcomingGames[i].id === id) return upcomingGames[i];
  }
}

function showMatchup() {
  var game = findGame(activeGameId);

  /* team headers */
  document.getElementById("homeHead").innerHTML =
    '<span class="team-logo" style="--c:' + game.home.color + '">' + game.home.abbr + "</span>" +
    '<div><div class="bold">' + game.home.abbr + '</div><div class="muted tiny">' + game.home.record + "</div></div>";

  document.getElementById("awayHead").innerHTML =
    '<span class="team-logo" style="--c:' + game.away.color + '">' + game.away.abbr + "</span>" +
    '<div class="right"><div class="bold">' + game.away.abbr + '</div><div class="muted tiny">' + game.away.record + "</div></div>";

  /* stat rows */
  var rowsHtml = "";
  for (var i = 0; i < statRows.length; i++) {
    var row = statRows[i];
    var hv = game.homeStats[row.key];
    var av = game.awayStats[row.key];
    /* for goals against, lower is better */
    var homeBetter = row.key === "goalsAgainst" ? hv < av : hv > av;
    var suffix = row.suffix || "";

    rowsHtml +=
      "<div>" +
        '<div class="stat-line-labels">' +
          '<span class="stat-val ' + (homeBetter ? "win-home" : "") + '">' + hv + suffix + "</span>" +
          '<span class="mid">' + row.label + "</span>" +
          '<span class="stat-val ' + (!homeBetter ? "win-away" : "") + '">' + av + suffix + "</span>" +
        "</div>" +
        '<div class="stat-bars">' +
          '<div class="bar-track left"><div class="bar-fill" style="width:' + (hv / row.max * 100) + "%;background:" + game.home.color + '"></div></div>' +
          '<div class="bar-track"><div class="bar-fill" style="width:' + (av / row.max * 100) + "%;background:" + game.away.color + '"></div></div>' +
        "</div>" +
      "</div>";
  }
  document.getElementById("statRows").innerHTML = rowsHtml;

  /* confidence ring */
  var homeFav = game.homeWinProb >= 50;
  var favTeam = homeFav ? game.home : game.away;
  var edge = homeFav ? game.homeWinProb : 100 - game.homeWinProb;

  var circ = 2 * Math.PI * 64;
  var confCircle = document.getElementById("confCircle");
  confCircle.style.strokeDasharray = circ;
  confCircle.style.strokeDashoffset = circ - (game.confidence / 100) * circ;
  confCircle.setAttribute("stroke",
    game.confidence >= 75 ? "var(--green)" : game.confidence >= 60 ? "var(--primary)" : "var(--gold)");

  document.getElementById("confNum").innerHTML = game.confidence + '<span class="conf-pct">%</span>';

  document.getElementById("confWinner").innerHTML =
    '<span class="team-logo" style="--c:' + favTeam.color + '">' + favTeam.abbr + "</span>" +
    '<div class="left"><p class="bold small">' + favTeam.city + " " + favTeam.name + "</p>" +
    '<p class="muted tiny">Projected winner · ' + edge + "% win prob</p></div>";
}

buildMatchupTabs();
showMatchup();


/* ===========================================================
   4) LEADERBOARD
   =========================================================== */
function trendIcon(trend) {
  if (trend === "up") return '<span style="color:var(--green)">▲</span>';
  if (trend === "down") return '<span style="color:var(--live)">▼</span>';
  return '<span class="muted">—</span>';
}

function buildPodium() {
  /* show 2nd, 1st, 3rd so first place sits in the middle */
  var order = [leaderboard[1], leaderboard[0], leaderboard[2]];
  var html = "";
  for (var i = 0; i < order.length; i++) {
    var p = order[i];
    var isFirst = p.rank === 1;
    html +=
      '<div class="podium-card glass ' + (isFirst ? "first" : "") + '">' +
        (isFirst ? '<span class="crown">👑</span>' : "") +
        '<span class="avatar" style="--h:' + p.hue + '">' + initials(p.user) + "</span>" +
        '<p class="podium-name">' + p.user + "</p>" +
        '<p class="muted tiny">Rank #' + p.rank + "</p>" +
        '<div class="podium-stats">' +
          '<div><div class="mono acc">' + p.accuracy + '%</div><div class="muted">accuracy</div></div>' +
          '<div><div class="mono">' + (p.points / 1000).toFixed(1) + 'k</div><div class="muted">points</div></div>' +
        "</div>" +
      "</div>";
  }
  document.getElementById("podium").innerHTML = html;
}

function buildBoard() {
  var html = "";
  for (var i = 0; i < leaderboard.length; i++) {
    var p = leaderboard[i];
    var medal = p.rank === 1 ? "🏆" : p.rank === 2 ? "🥈" : p.rank === 3 ? "🥉" : p.rank;
    html +=
      '<div class="board-row board-body-row">' +
        '<span class="rank-cell">' + medal + "</span>" +
        '<div class="board-user">' +
          '<span class="avatar" style="--h:' + p.hue + '">' + initials(p.user) + "</span>" +
          '<div><p class="bold">' + p.user + "</p>" +
          '<p class="mobile-sub">' + p.accuracy + "% · " + p.points.toLocaleString() + " pts</p></div>" +
        "</div>" +
        '<span class="board-acc hide-mobile">' + p.accuracy + "%</span>" +
        '<span class="board-streak hide-mobile">' + (p.streak > 0 ? "🔥" : "") + p.streak + "</span>" +
        '<span class="board-points">' + p.points.toLocaleString() + " " + trendIcon(p.trend) + "</span>" +
      "</div>";
  }
  document.getElementById("boardBody").innerHTML = html;
}

buildPodium();
buildBoard();


/* ===========================================================
   5) DISCUSSION (comments)
   =========================================================== */
var contextGame = upcomingGames[0]; /* TBL vs FLA */
var myPick = "away";
var likedComments = {}; /* remember which ones the user liked */

/* pick toggle buttons */
var pickBtns = document.querySelectorAll(".pick-btn");
for (var p = 0; p < pickBtns.length; p++) {
  pickBtns[p].onclick = function () {
    for (var k = 0; k < pickBtns.length; k++) {
      pickBtns[k].classList.remove("active");
    }
    this.classList.add("active");
    myPick = this.getAttribute("data-pick");
  };
}

function buildComments() {
  var html = "";
  for (var i = 0; i < comments.length; i++) {
    var c = comments[i];
    var team = c.pick === "home" ? contextGame.home : contextGame.away;
    var isLiked = likedComments[i] ? "liked" : "";

    html +=
      '<div class="comment glass">' +
        '<span class="avatar" style="--h:' + (c.hue || 200) + '">' + initials(c.user) + "</span>" +
        '<div class="comment-body">' +
          '<div class="comment-head">' +
            '<span class="bold">' + c.user + "</span>" +
            '<span class="pick-badge" style="color:' + team.color +
              ";background:" + team.color + '30">picks ' + team.abbr + "</span>" +
            '<span class="muted tiny">' + c.time + "</span>" +
          "</div>" +
          '<p class="comment-text">' + c.text + "</p>" +
          '<button class="like-btn ' + isLiked + '" data-index="' + i + '">♥ ' + c.likes + "</button>" +
        "</div>" +
      "</div>";
  }
  document.getElementById("comments").innerHTML = html;
  document.getElementById("commentCount").textContent = comments.length;

  /* hook up the like buttons */
  var likeBtns = document.querySelectorAll(".like-btn");
  for (var j = 0; j < likeBtns.length; j++) {
    likeBtns[j].onclick = function () {
      var idx = parseInt(this.getAttribute("data-index"), 10);
      if (likedComments[idx]) {
        comments[idx].likes -= 1;
        likedComments[idx] = false;
      } else {
        comments[idx].likes += 1;
        likedComments[idx] = true;
      }
      buildComments();
    };
  }
}

/* posting a new comment */
var composer = document.getElementById("composer");
composer.onsubmit = function (e) {
  e.preventDefault();
  var box = document.getElementById("commentText");
  var text = box.value.trim();
  if (text === "") return;

  /* add the new comment to the top of the list */
  comments.unshift({
    user: "You", hue: 200, time: "now",
    text: text, likes: 0, pick: myPick
  });
  box.value = "";
  buildComments();
};

buildComments();


/* ===========================================================
   6) LIVE GAME (animated chart + feed)
   =========================================================== */
var W = 640, H = 180, PAD = 8;
var maxMinute = liveTimeline[liveTimeline.length - 1].minute;
var step = 2; /* how many events are shown so far */

/* turn an event into an x/y point on the chart */
function pointFor(ev) {
  var x = PAD + (ev.minute / maxMinute) * (W - PAD * 2);
  var y = PAD + (1 - ev.homeProb / 100) * (H - PAD * 2);
  return { x: x, y: y };
}

function updateLiveGame() {
  var visible = liveTimeline.slice(0, step + 1);
  var current = liveTimeline[step];
  var prev = liveTimeline[step - 1] || current;
  var delta = current.homeProb - prev.homeProb;
  var awayProb = 100 - current.homeProb;

  /* update the win-prob bar + numbers */
  document.getElementById("homeProbBar").style.width = current.homeProb + "%";
  document.getElementById("awayProbBar").style.width = awayProb + "%";
  document.getElementById("homeProbText").textContent = current.homeProb + "%";
  document.getElementById("awayProbText").textContent = awayProb + "%";
  document.getElementById("chartBig").textContent = current.homeProb + "%";

  /* update the event note */
  document.getElementById("eventLabel").textContent = current.label;
  document.getElementById("eventDelta").textContent =
    "EDM win prob " + (delta >= 0 ? "+" : "") + delta + "% on this play";
  var arrow = document.getElementById("eventArrow");
  arrow.textContent = delta >= 0 ? "↗" : "↘";
  arrow.className = "event-arrow" + (delta >= 0 ? "" : " down");

  /* build the line + area path for the chart */
  var line = "";
  var pts = [];
  for (var i = 0; i < visible.length; i++) {
    var pt = pointFor(visible[i]);
    pts.push(pt);
    line += (i === 0 ? "M" : "L") + pt.x.toFixed(1) + "," + pt.y.toFixed(1) + " ";
  }
  document.getElementById("chartLine").setAttribute("d", line);

  if (pts.length > 1) {
    var last = pts[pts.length - 1];
    var first = pts[0];
    var area = line + "L" + last.x.toFixed(1) + "," + (H - PAD) +
               " L" + first.x.toFixed(1) + "," + (H - PAD) + " Z";
    document.getElementById("chartArea").setAttribute("d", area);

    /* move the glowing dot to the latest point */
    document.getElementById("chartDot").setAttribute("cx", last.x);
    document.getElementById("chartDot").setAttribute("cy", last.y);
    document.getElementById("chartDotGlow").setAttribute("cx", last.x);
    document.getElementById("chartDotGlow").setAttribute("cy", last.y);
  }

  /* show the last 3 events in the feed (newest first) */
  var feedHtml = "";
  var lastThree = visible.slice(-3).reverse();
  for (var j = 0; j < lastThree.length; j++) {
    var e = lastThree[j];
    var mm = e.minute < 10 ? "0" + e.minute : e.minute;
    feedHtml +=
      '<div class="feed-item">' +
        '<span><span class="muted mono">' + mm + "'</span> " + e.label + "</span>" +
        '<span class="mono">' + e.homeProb + "%</span>" +
      "</div>";
  }
  document.getElementById("eventFeed").innerHTML = feedHtml;
}

/* every couple seconds, reveal the next event (loops back around) */
function advanceLiveGame() {
  step = step + 1;
  if (step > liveTimeline.length - 1) {
    step = 2;
  }
  updateLiveGame();
}

updateLiveGame();
setInterval(advanceLiveGame, 2600);


/* ===========================================================
   7) FOOTER YEAR
   =========================================================== */
document.getElementById("copyYear").innerHTML =
  "© " + new Date().getFullYear() + " WinThePuck";
