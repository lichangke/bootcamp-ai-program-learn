# RAFlow (Phase 0)

This folder contains the Phase 0 baseline implementation for RAFlow.

## Included in Phase 0

- Tauri v2 app skeleton with React + TypeScript frontend
- Rust 2024 workspace dependency management
- System tray setup (`Settings`, `Quit`)
- Main window close-to-tray behavior
- Global shortcut registration skeleton
- Rust command bridge:
  - `ping`
  - `app_status`
- Logging bootstrap via `tracing` + `tracing-subscriber`
- Error skeleton via `thiserror`

## Run

```bash
cd w3/raflow
npm install
npm run tauri dev
```

## Frontend-only Build Check

```bash
cd w3/raflow
npm run build
```
