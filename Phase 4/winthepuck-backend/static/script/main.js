/* ===========================================================
   WinThePuck - front end JavaScript
   Phase 4: Back End Development

   In Phase 3 all of the data was written inside this file. Now the
   Flask back end sends the data instead, so this file only has to:
     1. open and close the mobile menu
     2. draw the confidence rings
     3. remember which team the discussion pick buttons chose
     4. ask the server for the live game and redraw the chart
   =========================================================== */


/* ===========================================================
   1) MOBILE MENU
   =========================================================== */
var menuBtn = document.getElementById("menuBtn");
var navLinks = document.getElementById("navLinks");

if (menuBtn && navLinks) {
  menuBtn.onclick = function () {
    navLinks.classList.toggle("open");
  };

  /* close the menu again after a link is clicked */
  var links = navLinks.getElementsByTagName("a");
  for (var i = 0; i < links.length; i++) {
    links[i].onclick = function () {
      navLinks.classList.remove("open");
    };
  }
}


/* ===========================================================
   2) CONFIDENCE RINGS

   The template writes the number into data-value and data-size,
   and this code turns it into a circle that is partly filled in.
   =========================================================== */
function ringColour(value) {
  if (value >= 75) {
    return "var(--green)";
  }
  if (value >= 60) {
    return "var(--primary)";
  }
  return "var(--gold)";
}

function drawRing(box) {
  var value = parseInt(box.getAttribute("data-value"), 10);
  var size = parseInt(box.getAttribute("data-size"), 10);

  /* a big ring gets a thicker line than a small one */
  var thickness = size > 100 ? 12 : 6;
  var radius = (size - thickness) / 2;
  var circumference = 2 * Math.PI * radius;
  var filled = circumference - (value / 100) * circumference;
  var middle = size / 2;
  var colour = ringColour(value);

  var html =
    '<svg width="' + size + '" height="' + size + '" style="transform:rotate(-90deg)">' +
      '<circle cx="' + middle + '" cy="' + middle + '" r="' + radius + '" fill="none" ' +
        'stroke="var(--secondary)" stroke-width="' + thickness + '"/>' +
      '<circle cx="' + middle + '" cy="' + middle + '" r="' + radius + '" fill="none" ' +
        'stroke="' + colour + '" stroke-width="' + thickness + '" stroke-linecap="round" ' +
        'stroke-dasharray="' + circumference + '" stroke-dashoffset="' + filled + '"/>' +
    "</svg>" +
    /* the number sits on top of the ring, so we pull it back up over it */
    '<div class="ring-number" style="margin-top:-' + size + "px;height:" + size + 'px">' +
      '<span class="mono bold" style="color:' + colour + '">' + value +
        (size > 100 ? '<span class="conf-pct">%</span>' : "") +
      "</span>" +
    "</div>";

  box.innerHTML = html;
}

var ringBoxes = document.getElementsByClassName("conf-ring-box");
for (var r = 0; r < ringBoxes.length; r++) {
  drawRing(ringBoxes[r]);
}


/* ===========================================================
   3) DISCUSSION PICK BUTTONS

   The buttons are not a normal form field, so when one is clicked
   we copy its team into the hidden input that gets sent to Flask.
   =========================================================== */
var pickButtons = document.querySelectorAll(".pick-toggle .pick-btn");
var pickValue = document.getElementById("pickValue");

for (var p = 0; p < pickButtons.length; p++) {
  pickButtons[p].onclick = function () {
    for (var k = 0; k < pickButtons.length; k++) {
      pickButtons[k].classList.remove("active");
    }
    this.classList.add("active");
    pickValue.value = this.getAttribute("data-pick");
  };
}


/* ===========================================================
   4) LIVE GAME

   Every few seconds we ask the back end for the next event of the
   live game and redraw the scoreboard, the bar and the chart.
   =========================================================== */
var liveCard = document.getElementById("liveCard");

/* the size of the chart, matching the viewBox in index.html */
var CHART_WIDTH = 640;
var CHART_HEIGHT = 180;
var CHART_PADDING = 8;

/* turn one event into an x / y point on the chart */
function pointFor(event, lastMinute) {
  var x = CHART_PADDING + (event.minute / lastMinute) * (CHART_WIDTH - CHART_PADDING * 2);
  var y = CHART_PADDING + (1 - event.home_prob / 100) * (CHART_HEIGHT - CHART_PADDING * 2);
  return { x: x, y: y };
}

function drawChart(events) {
  if (events.length === 0) {
    return;
  }

  /* the last minute on the chart, so the line always fills the width */
  var lastMinute = events[events.length - 1].minute;
  if (lastMinute === 0) {
    lastMinute = 1;
  }

  var line = "";
  var points = [];
  for (var i = 0; i < events.length; i++) {
    var point = pointFor(events[i], lastMinute);
    points.push(point);
    line += (i === 0 ? "M" : "L") + point.x.toFixed(1) + "," + point.y.toFixed(1) + " ";
  }
  document.getElementById("chartLine").setAttribute("d", line);

  if (points.length > 1) {
    var first = points[0];
    var last = points[points.length - 1];

    /* the shaded area is the same line, closed off along the bottom */
    var area = line +
      "L" + last.x.toFixed(1) + "," + (CHART_HEIGHT - CHART_PADDING) +
      " L" + first.x.toFixed(1) + "," + (CHART_HEIGHT - CHART_PADDING) + " Z";
    document.getElementById("chartArea").setAttribute("d", area);

    /* move the glowing dot to the newest point */
    document.getElementById("chartDot").setAttribute("cx", last.x);
    document.getElementById("chartDot").setAttribute("cy", last.y);
    document.getElementById("chartDotGlow").setAttribute("cx", last.x);
    document.getElementById("chartDotGlow").setAttribute("cy", last.y);
  }
}

function drawFeed(events, homeAbbr) {
  /* show the three newest events, newest at the top */
  var newest = events.slice(-3).reverse();
  var html = "";

  for (var i = 0; i < newest.length; i++) {
    var event = newest[i];
    var minute = event.minute < 10 ? "0" + event.minute : event.minute;
    html +=
      '<div class="feed-item">' +
        "<span><span class=\"muted mono\">" + minute + "'</span> " + event.label + "</span>" +
        '<span class="mono">' + event.home_prob + "%</span>" +
      "</div>";
  }

  document.getElementById("eventFeed").innerHTML = html;
}

function showLiveGame(live) {
  /* scoreboard */
  document.getElementById("homeScore").textContent = live.home_score;
  document.getElementById("awayScore").textContent = live.away_score;
  document.getElementById("liveMinute").textContent = live.minute;

  /* win probability bar and numbers */
  document.getElementById("homeProbBar").style.width = live.home_prob + "%";
  document.getElementById("awayProbBar").style.width = live.away_prob + "%";
  document.getElementById("homeProbText").textContent = live.home_prob + "%";
  document.getElementById("awayProbText").textContent = live.away_prob + "%";
  document.getElementById("chartBig").textContent = live.home_prob + "%";

  /* the note about the last thing that happened */
  document.getElementById("eventLabel").textContent = live.event_label;
  document.getElementById("eventDelta").textContent =
    live.home_abbr + " win prob " + (live.change >= 0 ? "+" : "") + live.change + "% on this play";

  var arrow = document.getElementById("eventArrow");
  if (live.change >= 0) {
    arrow.textContent = "↗";
    arrow.className = "event-arrow";
  } else {
    arrow.textContent = "↘";
    arrow.className = "event-arrow down";
  }

  drawChart(live.events);
  drawFeed(live.events, live.home_abbr);
}

/* ask the Flask back end for the next moment of the game */
function loadLiveGame() {
  fetch("/api/live")
    .then(function (response) {
      if (!response.ok) {
        throw new Error("The live game could not be loaded");
      }
      return response.json();
    })
    .then(function (live) {
      showLiveGame(live);
    })
    .catch(function (error) {
      /* if the server is not answering we just leave the last numbers up */
      console.log(error.message);
    });
}

if (liveCard) {
  /* draw the chart from the events Flask put in the page, so nothing
     is blank while we wait for the first answer from the server */
  var startingEvents = JSON.parse(liveCard.getAttribute("data-events"));
  drawChart(startingEvents);
  drawFeed(startingEvents, liveCard.getAttribute("data-home-abbr"));

  /* then keep asking the back end for the next event */
  setInterval(loadLiveGame, 2600);
}
