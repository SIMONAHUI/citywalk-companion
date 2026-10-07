#!/bin/zsh
set -eu
cd "${0:A:h}"
if [[ "$(uname)" != Darwin ]]; then echo 'CityWalk Companion currently requires macOS.'; exit 1; fi
citywalk_python=''
for citywalk_candidate in python3.12 python3.13 python3.14 python3; do
 if command -v "$citywalk_candidate" >/dev/null && "$citywalk_candidate" -c 'import sys; assert sys.version_info >= (3,12)' 2>/dev/null; then
  citywalk_python="$(command -v "$citywalk_candidate")"; break
 fi
done
if [[ -z "$citywalk_python" ]]; then echo 'Install Python 3.12 or newer from python.org, then run this installer again.'; exit 1; fi
"$citywalk_python" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./build-native.sh
printf '\nBuild complete. Open CityWalk Companion.app in this folder.\n'
