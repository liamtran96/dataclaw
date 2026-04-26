# DataClaw 0.4.2

This release adds the macOS menu-bar app distribution path for DataClaw.

## What's New

- Signed macOS app release workflow for Apple Silicon Macs.
- Direct GitHub Release download for Apple Silicon Macs:
  - `DataClaw-macOS-Apple-Silicon.dmg`
- Bundled PyInstaller sidecar so Mac app users do not need to install Python or the CLI separately.
- Tauri updater support through a signed `latest.json` release asset.
- Release documentation covering signing, notarization, updater credentials, and verification.

## Install

Download the latest Apple Silicon DMG:

https://github.com/peteromallet/dataclaw/releases/latest/download/DataClaw-macOS-Apple-Silicon.dmg

Intel Mac users can use the CLI install for now.
