# Recreate the Cronoscope environment

## Supported baseline

The verified environment is Linux with **Python 3.12.3**. Do not replace the project’s existing `.venv`; it remains the known-good baseline. The dependency files pin direct packages observed in that environment on 2026-10-29.

| File | Use |
| --- | --- |
| `requirements-web.txt` | Required to run the Pipeline 1–7 web application. |
| `requirements-dev.txt` | Optional regression and browser-testing tools. |
| `requirements-research.txt` | Optional exploratory/archival research tooling; not needed for normal viewing. |

## Recreate on another Linux computer

```bash
cd /path/to/spherex_feasibility
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
python -m web_app.api
```

The browser test package downloads its own Chromium runtime into the user’s Playwright cache. It is a development dependency, not a requirement for ordinary application use. If you do not need browser tests, omit both the development install and browser download.

For historical research scripts, additionally run:

```bash
python -m pip install -r requirements-research.txt
```

## Verification

Run `python -m pytest`. The current post-viewer baseline is 160 tests: the core scientific/evidence suite plus two browser-level tests. A passing test suite confirms saved-data replay and contracts, not live IRSA availability.

## Notes and boundaries

- These direct pins avoid broad upgrades. Pip resolves transitive dependencies appropriate to the selected platform/Python version.
- Python wheels and browser binaries are platform-dependent; recreate the environment on supported Linux rather than copying `.venv` between machines.
- `fastapi` and `matplotlib` existed in the original virtual environment but are not on the normal `web_app.api` import path. Matplotlib is listed as research-only; FastAPI is presently unused by the application.
- The test runner and Playwright were added for regression coverage. No system Python or OS package was changed.
- `python -m web_app.api` is the application launcher; Node/npm are not needed at runtime.
