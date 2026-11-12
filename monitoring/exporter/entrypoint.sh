#!/bin/sh
set -e

# Start the metrics exporter in the background; keep nginx as the
# container's main (foreground) process so restart/healthcheck semantics
# are unchanged from before.
python3 /opt/exporter.py &

exec nginx -g 'daemon off;'
