# Tauri desktop wrapper

This project can now run both as a normal Vite web app and as a Tauri desktop shell.

## Development

Run either:

```bash
npm run dev
```

for browser development, or:

```bash
npm run tauri:dev
```
This command now clears any existing processes on ports `5173` and `3001` before launching Tauri.

for desktop development.

When using [`npm run tauri:dev`](package.json:10), Tauri now attempts to start the backend automatically.

## Production build

Build the frontend and desktop shell with:

```bash
npm run tauri:build
```

On macOS, the Tauri bundle target is restricted to the application bundle (`"targets": ["app"]`), avoiding the DMG packaging step which often fails. Run [`npm run tauri:install`](package.json:13) to build and launch the app directly.

## API behavior

- Browser development uses the Vite proxy from [`vite.config.ts`](vite.config.ts).
- Packaged Tauri builds default the frontend API base URL to `http://127.0.0.1:3001/api`.
- The backend CORS allowlist in [`backend/app/config/settings.py`](backend/app/config/settings.py) includes Tauri window origins.
- You can override the API endpoint with `VITE_API_BASE_URL`.

## Backend process management

- Tauri starts the backend from [`backend/app/desktop_entry.py`](backend/app/desktop_entry.py:1).
- In local development it first tries `uv run --project backend python -m app.desktop_entry` from the repository root.
- If `uv` is unavailable, it falls back to `python3 -m app.desktop_entry` from the [`backend`](backend) directory.
- `SCYTHE_BACKEND_PORT` controls the backend listening port (defaults to `3001`).
- Backend startup is now asynchronous in [`src-tauri/src/lib.rs`](src-tauri/src/lib.rs:1), so the desktop window can open immediately even if the Python server is still booting or fails to start.
- On app exit, the spawned backend process is terminated by [`src-tauri/src/lib.rs`](src-tauri/src/lib.rs:1).

## Notes

- Tauri now launches the backend automatically for desktop runs.
- Browser-only development with [`npm run dev`](package.json:7) still requires starting the backend manually.
- Packaged apps include the backend source as a Tauri resource, but still rely on an available Python runtime and installed backend dependencies on the target machine.
