#!/bin/bash
set -e

DATA_DIR="/emulator-data/export"
mkdir -p "$DATA_DIR"

term_handler() {
  echo "Termination signal received. Exporting Firebase emulators..."
  firebase emulators:export "$DATA_DIR" --project demo-vixenone || true
  if [ -n "$PID" ]; then
    kill -INT "$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  echo "Firebase emulators shut down cleanly."
  exit 0
}

trap term_handler SIGTERM SIGINT

if [ -f "$DATA_DIR/firebase-export-metadata.json" ]; then
  echo "Found existing emulator export in $DATA_DIR. Starting with --import..."
  firebase emulators:start --project demo-vixenone --import "$DATA_DIR" --export-on-exit "$DATA_DIR" &
else
  echo "No existing export found in $DATA_DIR. Starting fresh with --export-on-exit..."
  firebase emulators:start --project demo-vixenone --export-on-exit "$DATA_DIR" &
fi

PID=$!
wait "$PID"
