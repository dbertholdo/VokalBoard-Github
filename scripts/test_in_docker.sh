#!/usr/bin/env bash
# Runs the pytest suite in a throwaway container against ISOLATED databases,
# never the dev database (maestro_cantor) and never production.
#
# Why a separate container: the web image bakes the code in (no bind mount —
# Google Drive folders break Docker bind mounts, see docker-compose.yml), and
# it has no pytest. This copies the current app/, tests/ and db/ into a
# `vb-test` container on the compose network and runs pytest there.
#
# Requires: `docker compose up -d db web` (the web image must be built).
#
# Usage (from the repo root, Git Bash / Linux / macOS):
#   scripts/test_in_docker.sh                      # full suite, quiet
#   scripts/test_in_docker.sh tests/test_x.py      # one file
#   scripts/test_in_docker.sh --recreate ...       # rebuild container + test DBs
#                                                  # (needed after db/schema.sql changes)
#
# Two test databases are used:
#   vokalboard_test               — main suite
#   vokalboard_retention_test     — tests/test_retention.py only skips unless the
#                                   DB name contains "retention_test", so it runs
#                                   there as a second pass on full-suite runs.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # stop Git Bash rewriting /code, /tmp paths

cd "$(dirname "$0")/.."
DB_CONTAINER=$(docker compose ps -q db)
NETWORK=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$DB_CONTAINER")
IMAGE=$(docker inspect -f '{{.Config.Image}}' "$(docker compose ps -q web)")
URL_BASE=postgresql+psycopg2://maestro_user:maestro_pass@db:5432
PYTEST_OPTS=(-q --tb=short -p no:warnings --show-capture=no)

fresh_db() {  # drop + create + load current schema
  docker exec "$DB_CONTAINER" dropdb -U maestro_user --if-exists --force "$1"
  docker exec "$DB_CONTAINER" createdb -U maestro_user "$1"
  docker cp db/schema.sql "$DB_CONTAINER":/tmp/schema_test.sql
  docker exec "$DB_CONTAINER" psql -q -U maestro_user -d "$1" -v ON_ERROR_STOP=1 -f /tmp/schema_test.sql >/dev/null 2>&1
}

RECREATE=0
if [ "${1:-}" = "--recreate" ]; then RECREATE=1; shift; fi
if ! docker inspect vb-test >/dev/null 2>&1; then RECREATE=1; fi

if [ $RECREATE = 1 ]; then
  echo "Recreating vb-test container and test databases..."
  fresh_db vokalboard_test
  fresh_db vokalboard_retention_test
  docker rm -f vb-test >/dev/null 2>&1 || true
  docker run -d --name vb-test --network "$NETWORK" \
    -e DATABASE_URL="$URL_BASE/vokalboard_test" \
    -e SECRET_KEY=dev-secret-key-change-in-production \
    -e EMAIL_BACKEND=console \
    "$IMAGE" sleep infinity >/dev/null
  docker cp requirements.txt vb-test:/code/
  docker cp requirements-dev.txt vb-test:/code/
  # The web image may predate the current requirements.txt — install both.
  docker exec vb-test pip install -q -r /code/requirements.txt -r /code/requirements-dev.txt >/dev/null 2>&1
fi

docker exec vb-test sh -c 'rm -rf /code/app /code/tests /code/db'
for d in app tests db; do docker cp "$d" vb-test:/code/; done

if [ $# -eq 0 ]; then
  docker exec -w /code vb-test python -m pytest tests "${PYTEST_OPTS[@]}"
  echo "--- retention pass ---"
  docker exec -w /code -e DATABASE_URL="$URL_BASE/vokalboard_retention_test" \
    vb-test python -m pytest tests/test_retention.py "${PYTEST_OPTS[@]}"
else
  docker exec -w /code vb-test python -m pytest "$@" "${PYTEST_OPTS[@]}"
fi
