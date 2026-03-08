#!/bin/sh
set -e

if [ -n "${DATABASE_URL}" ]; then
  echo "Waiting for PostgreSQL..."
  python - <<'PYCODE'
import os
import time

import psycopg

database_url = os.getenv("DATABASE_URL", "")
if not database_url:
    raise SystemExit(0)

max_tries = 30
for attempt in range(1, max_tries + 1):
    try:
        with psycopg.connect(database_url, connect_timeout=3):
            print("PostgreSQL is available.")
            break
    except Exception as exc:
        print(f"PostgreSQL not ready ({attempt}/{max_tries}): {exc}")
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL did not become available in time.")
PYCODE
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
