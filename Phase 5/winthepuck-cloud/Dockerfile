# ===========================================================
# WinThePuck website
#
# Built in two stages. The first installs the Python packages; the second
# copies the finished packages across and leaves the compiler, the package
# index cache and everything else used to build them behind. The result is a
# smaller image with less in it that could go wrong.
# ===========================================================

# ---- stage 1: install the dependencies -------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /install

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt


# ---- stage 2: the image that actually runs ---------------------------------
FROM python:3.12-slim

# Anything that goes wrong should appear in the logs straight away rather than
# sitting in a buffer, and there is no point writing .pyc files into a
# container that gets thrown away.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WINTHEPUCK_DATA_DIR=/data

# Run as an ordinary user. If anything ever does get in through the web app,
# it arrives without permission to change the application it is running in.
RUN useradd --create-home --shell /bin/bash winthepuck

COPY --from=builder /install/deps /usr/local

WORKDIR /app
COPY --chown=winthepuck:winthepuck . .

# The database is built on first start and has to outlive the container, so it
# lives on a volume rather than in the image's own filesystem.
RUN mkdir -p /data && chown winthepuck:winthepuck /data
VOLUME ["/data"]

USER winthepuck
EXPOSE 8000

# Docker restarts the container by itself if this stops answering. It calls the
# same /healthz the Azure deployment uses, which checks the database is really
# there rather than just that the process is alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "app:app", \
     "--bind=0.0.0.0:8000", \
     "--workers=2", \
     "--threads=4", \
     "--timeout=120", \
     "--access-logfile=-", \
     "--error-logfile=-"]
