#!/bin/zsh
set -eu
cd "${0:A:h}"
mkdir -p 'CityWalk Captions.app/Contents/MacOS' 'CityWalk Companion.app/Contents/MacOS'
cp ViewerInfo.plist 'CityWalk Companion.app/Contents/Info.plist'
cp CaptionsInfo.plist 'CityWalk Captions.app/Contents/Info.plist'
swiftc CaptionOverlay.swift -o 'CityWalk Captions.app/Contents/MacOS/CityWalkCaptions'
swiftc -parse-as-library RecordWebVoice.swift -o RecordWebVoice
swiftc CityWalkViewer.swift -o 'CityWalk Companion.app/Contents/MacOS/CityWalkViewer'
codesign --force --sign - 'CityWalk Captions.app'
codesign --force --sign - 'CityWalk Companion.app'
