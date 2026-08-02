#!/usr/bin/env bash
set -euo pipefail

# Merge the Secrets Manager env JSON blob (DRAFTLY_ENV_JSON) into the environment.
if [[ -n "${DRAFTLY_ENV_JSON:-}" ]]; then
  eval "$(
    python3 - <<'PY'
import json
import os

env = json.loads(os.environ["DRAFTLY_ENV_JSON"])
for key, value in env.items():
    print(f"export {key}={json.dumps(str(value))}")
PY
  )"
fi

# Materialize the GitHub App private key from base64 (never baked into the image).
if [[ -n "${GITHUB_PRIVATE_KEY_B64:-}" ]]; then
  printf "%s" "${GITHUB_PRIVATE_KEY_B64}" | base64 -d > /app/private-key.pem
  chmod 600 /app/private-key.pem
  export GITHUB_PRIVATE_KEY_PATH=/app/private-key.pem
fi

exec /app/.venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000
