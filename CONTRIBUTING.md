# Contributing to Urban Twin

Thanks for considering a contribution. This project is a Kensington,
Calgary neighbourhood digital twin — ingest pipeline, forecasting models,
and an interactive 3D map. Contributions of any size are welcome: bug
fixes, docs, new data layers, forecast improvements, or drone/sim work.

## Before you start

- Check open [issues](https://github.com/VyapakBansal/Urban-Twin/issues)
  and [pull requests](https://github.com/VyapakBansal/Urban-Twin/pulls)
  to avoid duplicate work.
- For anything larger than a small fix (new feature, architectural
  change, new data source), open an issue first to discuss the approach
  before writing code.

## Development setup

Follow the [Quick start](README.md#quick-start) in the README:

```
git clone https://github.com/VyapakBansal/Urban-Twin.git
cd Urban-Twin
cp .env.example .env
# Set OPENWEATHER_API_KEY=...

python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"

npm run dev
```

Optional: drone/PX4 setup is in [docs/DRONE.md](docs/DRONE.md) — only
needed if your change touches the drone/telemetry layer.

## Making a change

1. Fork the repo and create a branch off `main`:
   `git checkout -b your-feature-name`
2. Keep changes focused — one logical change per PR.
3. Match existing code style:
   - Python: type hints, Pydantic models for validation, parameterized
     SQL (no string-built queries).
   - TypeScript/React: match existing component structure in `frontend/`.
4. Run relevant checks before opening a PR:
   - `npm run validate` — forecast metrics sanity check (if you touched
     `urban_twin/forecast/`)
   - Any tests under `tests/`
5. Update docs if your change affects setup, configuration, or the API
   surface (`README.md`, relevant file under `docs/`).

## Commit messages

Keep them short and descriptive (e.g. `fix: correct river level unit
conversion`, `feat: add PM10 layer`). No strict convention enforced, but
clarity matters more than format.

## Submitting a pull request

- Describe what changed and why.
- Reference any related issue (`Fixes #12`).
- Include screenshots/GIFs for frontend or map changes where relevant.
- Be responsive to review feedback — this is a small solo-maintained
  project, so turnaround may take a few days.

## Reporting bugs / security issues

- Regular bugs: open a GitHub issue with steps to reproduce, expected
  vs actual behavior, and environment details (OS, Python/Node version).
- Security issues: see [SECURITY.md](SECURITY.md) — do not open a public
  issue for anything sensitive.

## Data and licensing

This project consumes data from OpenStreetMap, OpenWeather, Environment
Canada, and Open-Meteo, each under its own terms — see the data section
in [LICENSE.md](LICENSE.md). If your contribution adds a new data
source, note its license/terms in your PR description.

## Code of conduct

Be respectful and constructive. No formal code of conduct is enforced
yet, but standard open-source etiquette applies.
