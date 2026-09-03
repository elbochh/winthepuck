# The daily prediction job
#
# Separate from the website on purpose. This image carries scikit-learn,
# CatBoost and numpy, which together are far larger than the website itself.
# Keeping them apart is what lets the website fit on Azure's free tier while
# the model runs on a GitHub Actions runner.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --shell /bin/bash modeluser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=modeluser:modeluser . .

USER modeluser

# Reads SITE_URL and REFRESH_TOKEN from the environment, the same two settings
# the GitHub Actions workflow passes in.
ENTRYPOINT ["sh", "-c", "python refresh_predictions.py \
  --days-ahead 14 --history-days 21 --out refresh_payload.json \
  ${SITE_URL:+--post \"$SITE_URL\"} ${REFRESH_TOKEN:+--token \"$REFRESH_TOKEN\"}"]
