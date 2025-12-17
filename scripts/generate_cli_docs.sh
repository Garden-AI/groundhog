#!/usr/bin/env bash
# Generate CLI documentation from typer app
# This script regenerates docs/api/cli.md from the typer CLI definition

set -e

cd "$(dirname "$0")/.."

echo "Generating CLI documentation..."
uv run typer groundhog_hpc.app.main utils docs --title "Groundhog CLI Reference" --name hog --output docs/api/cli.md

echo "CLI documentation generated at docs/api/cli.md"
