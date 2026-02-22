#!/bin/sh
set -e

# Validate that DB_PASSWORD is set to a real secret value
if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "CHANGE_ME" ]; then
  echo "ERROR: DB_PASSWORD must be set to a secure value" >&2
  exit 1
fi

# Ensure uploads directory exists and is writable by appuser.
# Docker named volumes may mount over /app/uploads with root ownership,
# overriding the permissions set during image build.
mkdir -p /app/uploads
chown -R appuser:appgroup /app/uploads

# Drop to appuser and exec the main process
exec gosu appuser "$@"
