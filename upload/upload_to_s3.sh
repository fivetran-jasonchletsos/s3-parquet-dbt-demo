#!/usr/bin/env bash
set -euo pipefail

BUCKET="s3://jason-chletsos-parquet-dbt-demo"
PROFILE="pokemon-app"
DATA_DIR="/Users/jason.chletsos/Documents/GitHub/s3-parquet-dbt-demo/data/"

aws s3 sync "$DATA_DIR" "$BUCKET/raw/" --profile "$PROFILE"

echo
echo "Bucket contents:"
aws s3 ls "$BUCKET/raw/" --recursive --profile "$PROFILE"
