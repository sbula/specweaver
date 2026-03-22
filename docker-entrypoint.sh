#!/bin/sh
set -e

# Auto-register projects mounted under /projects
if [ -d /projects ]; then
    for dir in /projects/*/; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        uv run sw init "$name" --path "$dir" 2>/dev/null || true
    done
    # If no sub-dirs, register /projects itself
    if [ -z "$(ls -d /projects/*/ 2>/dev/null)" ]; then
        uv run sw init project --path /projects 2>/dev/null || true
    fi
fi

# Forward to sw command (exec replaces shell for signal handling)
exec uv run sw "$@"
