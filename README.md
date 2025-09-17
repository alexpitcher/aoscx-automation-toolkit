# CXEdit

CXEdit is a mobile‑first AOS‑CX automation dashboard built on Flask with a simple responsive UI for viewing switch status and managing VLANs and interfaces. The app defaults to the mobile UI and includes a minimal desktop view when explicitly requested.

## Quick Start

- Prereqs
  - Python 3.10+
  - pip / venv

- Setup
  - `python -m venv venv && source venv/bin/activate`
  - `pip install -r requirements.txt`
  - Copy `.env.example` to `.env` and adjust as needed:
    - `SWITCH_USER`, `SWITCH_PASSWORD`
    - `API_VERSION` (default: `10.15`)
    - `SSL_VERIFY` (`True` or `False`)
    - `FLASK_DEBUG` (`True` or `False`)

- Run
  - `python app.py`
  - App listens on `http://localhost:5001`
  - Default route redirects to mobile UI: `http://localhost:5001/`
  - Desktop view (optional): `http://localhost:5001/?desktop=true`

## Docker

- Build image locally
  - `docker build -t cxedit:local .`
  - `docker run --rm -p 5001:5001 --env-file .env cxedit:local`

- Using Compose
  - `docker compose up --build -d`
  - Visit `http://localhost:5001`

- Published image (GHCR)
  - Image: `ghcr.io/<owner>/aoscx-automation-toolkit:latest` or a version tag
  - Pull: `docker pull ghcr.io/<owner>/aoscx-automation-toolkit:v1.2`
  - Run: `docker run --rm -p 5001:5001 ghcr.io/<owner>/aoscx-automation-toolkit:v1.2`

Notes:
- The GitHub Actions workflow builds and publishes on pushes to `main` and when you create tags like `v1.2`.
- If the package is private by default, set visibility to public under GitHub Packages for this repo.

## UI Notes

- Mobile UI
  - Bottom navigation is opaque and safe‑area aware.
  - Header and titles display the app name: CXEdit.
  - Settings show the version: `CXEdit v1.1`.

- Desktop UI
  - Accessible only with `/?desktop=true`.

## Versioning

- Tags
  - `v1.0`: Baseline snapshot
  - `v1.1`: Mobile bottom nav opaque, default to mobile UI, CXEdit branding and settings version

- Push tags
  - `git push --follow-tags` or `git push origin v1.0 v1.1`

## Project Layout

- Backend: Flask app in `app.py`, configuration in `config/`
- Templates: `templates/mobile_dashboard.html`, `templates/dashboard.html`
- Static assets: `static/`
- Mobile React prototype (optional): `newui/`
