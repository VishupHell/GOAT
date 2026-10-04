#!/bin/sh
set -e

flask db upgrade
exec gunicorn --bind 0.0.0.0:8000 --workers 2 "app:create_app()"
