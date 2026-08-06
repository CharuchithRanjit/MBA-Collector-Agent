#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
UV=/home/ec2-user/.local/bin/uv

"$UV" run chief feed poll --all || echo "feed poll failed, continuing"
"$UV" run chief feed summarize --limit 25 || echo "feed summarize failed, continuing"
"$UV" run chief brief --send
