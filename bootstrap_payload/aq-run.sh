#!/bin/bash
# usage: aq-run.sh <target>   (target = key in targets.json)
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/venv/bin/python" "$HERE/aq_registry.py" run "${1:-}"
