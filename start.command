#!/bin/zsh
cd "${0:A:h}" || exit 1
.venv/bin/python app.py &
citywalk_server_pid=$!
trap 'kill -TERM "$citywalk_server_pid" 2>/dev/null' INT TERM HUP
sleep 1
open 'CityWalk Companion.app'
wait "$citywalk_server_pid"
