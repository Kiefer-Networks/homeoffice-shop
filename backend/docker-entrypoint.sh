#!/bin/sh
set -e

# Ensure uploads directory exists and is writable by appuser.
# Docker named volumes may mount over /app/uploads with root ownership,
# overriding the permissions set during image build.
mkdir -p /app/uploads
chown -R appuser:appgroup /app/uploads

# Drop to appuser and exec the main process
exec gosu appuser "$@"
