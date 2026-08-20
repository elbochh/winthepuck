#!/bin/bash
# Full data + model + export refresh chain.
# Run whenever new games have been played (e.g. daily during the season).
set -e
cd "$(dirname "$0")"

echo "=== 1/6 historical data refresh ==="
(cd ../nhl_data_pipeline && python3 main.py --mode historical)

echo "=== 2/6 rebuild merged modeling table ==="
(cd ../nhl_data_pipeline && python3 main.py --mode build-merged)

echo "=== 3/6 rebuild model dataset (Elo + decay features) ==="
python3 build_model_dataset.py

echo "=== 4/6 walk-forward evaluation (pregame model) ==="
python3 train_evaluate.py

echo "=== 5/6 live features + live model ==="
(cd ../nhl_data_pipeline && python3 main.py --mode build-live-features --start-season 20222023 --end-season 20252026)
python3 train_live_model.py

echo "=== 6/6 export website data ==="
python3 export_site_data.py

echo "ALL DONE"
