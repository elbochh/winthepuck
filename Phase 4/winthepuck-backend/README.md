# WinThePuck — Back End (Project Phase 4)

**Team:** The Goal Diggers — Moayed Mohamed, Bechir Elloumi, Abhishek Kumar

An NHL prediction website built with **Flask** and **SQLite**. The front end
from Phase 3 is still here, but every number on the screen now comes out of a
database instead of being written inside the JavaScript file.

---

## How to run it

You need Python 3 installed. From inside this folder:

```
pip install -r requirements.txt   # 1. install Flask
python seed_data.py               # 2. build the database (only the first time)
python app.py                     # 3. start the website
```

Then open **http://127.0.0.1:5000** in a browser.

To start over with fresh data, run `python seed_data.py` again — it deletes the
old tables and rebuilds them.

### Test account

| Username       | Password   |
| -------------- | ---------- |
| `FrozenOracle` | `puck1234` |

All six demo members use the same password. You can also create your own
account on the **Create an account** page.

---

## What is in each file

| File / folder     | What it does                                                          |
| ----------------- | --------------------------------------------------------------------- |
| `app.py`          | The Flask application. Every page and form of the website is in here.  |
| `database.py`     | Small helper functions for opening the database and running SQL.       |
| `scoring.py`      | The rules that turn a finished game into leaderboard points.           |
| `seed_data.py`    | Builds the database and fills it with teams, games, members and picks. |
| `schema.sql`      | The `CREATE TABLE` statements for all eight tables.                    |
| `winthepuck.db`   | The SQLite database itself (created by `seed_data.py`).                |
| `templates/`      | The HTML pages. `layout.html` holds the nav bar and footer.            |
| `static/styles/`  | `style.css` — the stylesheet from Phase 3 plus the new Phase 4 parts.  |
| `static/script/`  | `main.js` — the mobile menu, confidence rings and live game chart.     |
| `static/images/`  | `favicon.svg` — the site icon.                                         |

---

## Pages

| Address                | Page                                                    |
| ---------------------- | ------------------------------------------------------- |
| `/`                    | Home: hero, the live game, next games, top three members |
| `/games`               | Every upcoming game — save your own pick here            |
| `/matchups/<id>`       | Two teams compared stat by stat                          |
| `/leaderboard`         | Members ranked by points, accuracy and streak            |
| `/discussion/<id>`     | Post and like messages about a game                      |
| `/login`, `/register`  | Sign in or create an account                             |
| `/logout`              | Sign out                                                 |

### JSON API

`main.js` uses these to update the page without reloading it:

| Address            | What it sends back                                       |
| ------------------ | -------------------------------------------------------- |
| `/api/games`       | Every upcoming game and its prediction                   |
| `/api/live`        | The live game, moved on by one event each time it is called |
| `/api/leaderboard` | The leaderboard                                          |

---

## The database

Eight tables, defined in `schema.sql`:

- **teams** — the eight NHL teams and their season stats
- **games** — upcoming, live and finished games with the model prediction
- **live_events** — the play-by-play of the live game
- **live_state** — how far through the live game we are
- **users** — members and their hashed passwords
- **predictions** — every pick a member makes
- **comments** — discussion messages
- **comment_likes** — one row per like, so nobody can like twice

The leaderboard is **not** stored. It is worked out in SQL every time the page
is opened by joining `users` to `predictions`, counting the correct picks and
adding up the points.

---

## Notes

- Passwords are never stored as plain text. `werkzeug.security` hashes them
  when an account is made and checks the hash when somebody signs in.
- Every SQL query uses `?` placeholders, so a member cannot break the database
  by typing SQL into a form.
- Forms are checked on the server: empty messages, short passwords, duplicate
  usernames and teams that are not in the game are all rejected.
