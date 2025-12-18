# Markets Recon

AI pipeline for processing fund manager outlook PDFs into structured allocation intelligence.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# Run full pipeline
python -m pipeline.run --pdf <path>

# Run tests
pytest tests/ -v

# Type check
mypy src/ --strict
```

See `CLAUDE.md` for full documentation.
