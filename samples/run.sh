#!/usr/bin/env bash
# Launch the samples gallery — a web UI with a sample list on the left
# and an iframe on the right. Click a sample to start it.
#
# Env:
#   GALLERY_PORT (default 8000)  — port the gallery listens on
#   SAMPLE_PORT  (default 8080)  — port each sample is launched on
exec poetry run python "$(cd "$(dirname "$0")" && pwd)/gallery.py" "$@"
