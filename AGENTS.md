# krusch-authority-packs — Agent Guidelines & Invariants

> **Role**: Deterministic Legal & Commercial Statutory Authority Packs (16 Packs, 17 Mandates across 8 Domains)  
> **Stack**: Python 3.12, YAML/JSON Schemas, Pytest  
> **Last updated**: 2026-10-20

## 1. Architectural Invariants (`MUST` / `MUST NOT`)

1. **INV-01 (Schema & Temporal Integrity)**: Every YAML authority pack in `packs/` must validate against the canonical pack schema with explicit `jurisdiction`, `effective_date` / `as_of_date` bounds, statutory section citations, and floor/ceiling mandate rules.
2. **INV-02 (Mirror Synchronization)**: Changes to `packs/*.yaml` must remain synchronized with `projects/krusch-law/data/packs/` and `projects/krusch-gateway-mcp` (`PackRegistry` & `PackBinder`).
3. **INV-03 (Zero Hallucinated Citations)**: All statutory sections and remedies must trace to verbatim California, federal, or municipal authority text.

## 2. Verification
- **Run Tests**: `pytest`
