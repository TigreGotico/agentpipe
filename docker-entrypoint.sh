#!/bin/bash
set -e

echo "=== agentpipe server ==="
echo ""

# First-run provisioning: report which CLIs are installed and which have
# credentials, and create the config directories the installed ones need.
# It never writes credentials and never fails the boot — a container with no
# credentials at all still serves the free-tier kilo and opencode models.
if [ "$AGENTPIPE_SKIP_PROVISION" != "1" ]; then
    python -m agentpipe.provision || echo "  [WARN] provisioning report failed — starting anyway"
    echo ""
fi

echo "Starting server..."
exec "$@"
