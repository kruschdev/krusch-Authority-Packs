# Install `krusch-Authority-Packs`

These are instructions for a coding agent (Claude Code, Codex, Cursor, Windsurf, or Antigravity) that a person asked to install and verify `krusch-Authority-Packs` (`krusch-authority-packs` `v1.0.0`) on their machine.

`krusch-Authority-Packs` provides deterministic statutory, regulatory, accounting, and commercial rulebooks ("Authority Packs"), the `authority-pack` CLI validator, a fail-closed `PackBinder` (`src.binder`), span-grounded `SlotVerifier` (`src.slots`), compiled preemption DAG operators (`src.preemption`), and a 180-query conformance harness (`src.eval`). It runs 100% locally in Python (`pyyaml>=6.0` is the sole runtime dependency) with zero Docker containers, zero database servers, zero network calls, and zero API keys.

## 1. Check Prerequisites First (All at Once)

Run a single read-only check before making any changes:

```bash
id -u
python3 --version 2>/dev/null || echo "MISSING: python3"
python3 -m venv --help >/dev/null 2>&1 || echo "MISSING: python3-venv"
git --version 2>/dev/null || echo "MISSING: git"
```

Evaluate the results:
1. **User check**: If `id -u` prints `0` (`root`), stop and ask the person to run you under a standard non-root user account.
2. **Python `>= 3.11` recommended (`>= 3.10` supported) with `venv` (Required)**: If `python3` is missing, older than `3.10`, or lacks the `venv` module, ask the person before installing Python `3.11+` (`uv python install 3.12`, `pyenv`, `brew`, or OS packages).
3. **Zero External Services**: Neither Docker, PostgreSQL, Ollama, nor any cloud API key is needed.

## 2. Install in an Isolated Virtual Environment & Verify

Check `pwd` first so you clone into an appropriate workspace directory (for example, `$HOME/src/krusch-Authority-Packs` if `pwd` is `$HOME`). Preserve exact repository slug casing (`krusch-Authority-Packs`):

```bash
git clone https://github.com/kruschdev/krusch-Authority-Packs.git
cd krusch-Authority-Packs
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

Run the three offline verification gates in order:

```bash
# 1. Validate all 16 bundled YAML Authority Packs against schema and token-budget ceilings (<= 850 tokens/entry)
.venv/bin/authority-pack validate "packs/**/*.yaml"

# 2. Run the 180-query Binder Conformance Benchmark across all 5 adversarial query classes (0.0% Wrong-Law Blend)
.venv/bin/python -m src.eval

# 3. Run the automated pytest unit and conformance suite (68 tests)
.venv/bin/pytest tests/ -v
```

## 3. CLI & Python Library Usage

### Inspect Bundled Packs via CLI

Installing the package registers `.venv/bin/authority-pack` (and alias `.venv/bin/rag-pack`), matching `python3 -m src.validator`:

```bash
# Inspect municipal tenancy and accounting standards packs
.venv/bin/authority-pack info packs/legal/ca_oakland.yaml
.venv/bin/authority-pack info packs/legal/ca_los_angeles.yaml
.venv/bin/authority-pack info packs/accounting/biz_accounting_asc606.yaml
```

### Scaffold a New Authority Pack (Optional)

Only run `scripts/scaffold_pack.py` if the person asks to create a new jurisdiction, standards, or commercial pack:

```bash
.venv/bin/python scripts/scaffold_pack.py --help
```

### Embed in a Python Application (Optional)

If the person wants to wire `krusch-Authority-Packs` into another local Python project, install it editable into that project's virtual environment (`/path/to/app/.venv/bin/pip install -e /absolute/path/to/krusch-Authority-Packs`) and load packs through `RagPackValidator`:

```python
from src.validator import RagPackValidator

pack = RagPackValidator.load("packs/legal/ca_oakland.yaml")
print(pack.pack_id, len(pack.entries), pack.covered_topics)
```

## Never

- **Never run global `pip install` or `sudo pip`**: always install inside `.venv` (`python3 -m venv .venv && .venv/bin/pip install ...`).
- **Never run `authority-pack` or `pytest` as `root` or with `sudo`**.
- **Never mutate existing curated YAML files under `packs/`** unless the person explicitly asks to author or amend a pack; modifying statutory text or slot values without matching verbatim quotes breaks `SlotVerifier` fail-closed checks.
- **Never start Docker containers or invent `.env` files**: this library is stateless and offline by design.

## Tell the Person After

Share a concise status summary:
1. **Virtual environment & CLI path**: Report the clone directory and `.venv/bin/authority-pack` binary path.
2. **Pack validation**: Confirm all `16` YAML packs under `packs/` passed `authority-pack validate`.
3. **Benchmark & test status**: Confirm `.venv/bin/python -m src.eval` (`N = 180`, `0.0%` Wrong-Law Blend) and `.venv/bin/pytest tests/ -v` (`68/68` tests) passed cleanly.
4. **Quick try-it command**: Share `.venv/bin/authority-pack info packs/legal/ca_oakland.yaml` so the person can inspect typed statutory slots, covered topics, and uncovered refusal boundaries right away.
