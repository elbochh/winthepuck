#!/bin/bash
# How Azure App Service starts the website.
#
# gunicorn is the production web server. Flask's own server is only meant for
# development, so Azure uses this instead.
#   --bind 0.0.0.0:8000   Azure sends requests to port 8000
#   --workers 2           two copies of the app, so one slow page does not block
#   --threads 4           each copy can handle four requests at a time
#   --timeout 120         allow slow first requests while the database is built
exec gunicorn app:app \
  --bind=0.0.0.0:8000 \
  --workers=2 \
  --threads=4 \
  --timeout=120 \
  --access-logfile '-' \
  --error-logfile '-'
