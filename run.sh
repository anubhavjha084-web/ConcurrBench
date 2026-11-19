#!/usr/bin/env bash
# ---------------------------------------------------------------
# One-click launch for ConcurrencyBugBench (Unix/macOS)
# ---------------------------------------------------------------
set -e
echo "Building and starting the benchmark container..."
docker compose up --build
