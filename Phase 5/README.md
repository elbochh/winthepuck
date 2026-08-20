# Phase 5 — Cloud Deployment

**Live site:** https://winthepuck.azurewebsites.net

This folder contains everything that was added or changed to get WinThePuck
running in the cloud.

```
Phase 5/
├── winthepuck-cloud/     the Flask website that runs on Azure
├── model-service/        the model, and the job that refreshes predictions
├── docs/                 the two Word documents for this phase
└── .secrets/             tokens and the Azure publish profile (never committed)
```

---

## The idea in one paragraph

The website has to be small enough to fit on Azure's free tier, and our machine
learning stack (pandas, scikit-learn, CatBoost) is not small. So the website
does not run the model at all. Once a day, a job on a free GitHub runner loads
the trained model, asks the NHL's public API what has happened and what is
coming, works out the predictions, and posts them to the website. The website
just stores what it is sent and shows it.

---

## winthepuck-cloud — the website

| File | What it does |
|---|---|
| `app.py` | Every page and every form. |
| `config.py` | Settings, read from environment variables on Azure. |
| `database.py` | Opening SQLite and running queries. |
| `nhl_data.py` | Filling the database with real data, and applying each refresh. |
| `scoring.py` | Turning finished games into leaderboard points. |
| `schema.sql` | The tables. |
| `data/` | The real data the site builds itself from on first start. |
| `startup.sh` | How Azure starts gunicorn. |

Run it locally:

```bash
cd winthepuck-cloud
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # http://127.0.0.1:5000
```

The database builds itself on first start. Delete `instance/` to start over.

## model-service — the predictions

| File | When it runs | What it does |
|---|---|---|
| `build_serving_bundle.py` | Rarely, on a laptop | Retrains the ensemble and saves the model, the Elo state and the accuracy report into `serving/`. Needs the Phase 1 pipeline output. |
| `export_history.py` | Rarely, on a laptop | Exports the finished season and the playoff replay. |
| `refresh_predictions.py` | Every day, in the cloud | Predicts the upcoming games and posts them to the website. |
| `nhl_api.py` | — | A small client for the NHL's free API. |
| `elo.py` | — | The Elo rules from Phase 2. |
| `form_book.py` | — | Recent form worked out from real scores. |

Everything in `serving/` is under 700 KB in total, which is what lets the daily
job run without the 18 GB pipeline.

---

## Setting up GitHub (one time)

The two workflows in `.github/workflows/` need three repository secrets.
Add them under **Settings → Secrets and variables → Actions → New repository
secret**:

| Secret name | Value |
|---|---|
| `AZURE_WEBAPP_PUBLISH_PROFILE` | The whole contents of `Phase 5/.secrets/publish-profile.xml` |
| `WINTHEPUCK_URL` | `https://winthepuck.azurewebsites.net` |
| `REFRESH_TOKEN` | The `REFRESH_TOKEN` line from `Phase 5/.secrets/azure-app-secrets.txt` |

After that:

- pushing a change under `Phase 5/winthepuck-cloud/` deploys the site automatically
- the predictions refresh every day at 11:30 UTC
- you can run either workflow by hand from the **Actions** tab

> `Phase 5/.secrets/` is in `.gitignore` and must stay there. If a token ever
> leaks, generate a new one and update it in both Azure and GitHub.

---

## Useful commands

Deploy by hand, without GitHub:

```bash
cd winthepuck-cloud
zip -r ../app.zip . -x "instance/*" "__pycache__/*"
az webapp deploy --name winthepuck --resource-group rg-winthepuck \
  --src-path ../app.zip --type zip
```

Watch the live logs:

```bash
az webapp log tail --name winthepuck --resource-group rg-winthepuck
```

Check the site is healthy:

```bash
curl https://winthepuck.azurewebsites.net/healthz
```

Refresh the predictions by hand:

```bash
cd model-service
python3 refresh_predictions.py --days-ahead 30 \
  --post https://winthepuck.azurewebsites.net --token "$REFRESH_TOKEN"
```

Remove everything from Azure (this deletes the site and its database):

```bash
az group delete --name rg-winthepuck --yes
```
