"""
RagPack Validator & Loader: Enforces schema integrity, token budget constraints,
pre-extracted statutory/contractual slots, and preemption DAGs.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML is required for krusch-authority-packs. Install via `pip install pyyaml`.")


MAX_CHUNK_TOKEN_BUDGET = 850
REQUIRED_ROOT_KEYS = {"pack_id", "version", "publisher", "coverage", "description"}


class ValidationError(Exception):
    """Raised when a RAG pack violates schema or invariant rules."""
    pass


@dataclass
class StatutorySlot:
    name: str
    value: Any
    data_type: str


@dataclass
class AuthorityEntry:
    citation: str
    title: str
    topic: str
    authority_class: str
    raw_content: str
    slots: Dict[str, Any] = field(default_factory=dict)
    preempts: List[str] = field(default_factory=list)
    preempted_by: List[str] = field(default_factory=list)
    exceptions_ref: Optional[str] = None
    defines_terms: List[str] = field(default_factory=list)
    estimated_tokens: int = 0


@dataclass
class RagPack:
    pack_id: str
    version: str
    publisher: str
    description: str
    domain: Optional[str] = None
    state: Optional[str] = None
    municipality: Optional[str] = None
    county: Optional[str] = None
    covered_topics: List[str] = field(default_factory=list)
    known_uncovered_topics: List[str] = field(default_factory=list)
    entries: List[AuthorityEntry] = field(default_factory=list)
    raw_dict: Dict[str, Any] = field(default_factory=dict)

    def total_estimated_tokens(self) -> int:
        return sum(e.estimated_tokens for e in self.entries)

    def find_by_topic(self, topic: str) -> List[AuthorityEntry]:
        return [e for e in self.entries if e.topic.lower() == topic.lower()]

    def find_by_citation(self, citation: str) -> Optional[AuthorityEntry]:
        for e in self.entries:
            if e.citation.lower() == citation.lower() or citation.lower() in e.citation.lower():
                return e
        return None

    def all_slots(self) -> Dict[str, Any]:
        """Aggregate all pre-extracted slots across all entries."""
        merged: Dict[str, Any] = {}
        for entry in self.entries:
            for k, v in entry.slots.items():
                merged[f"{entry.citation}::{k}"] = v
        return merged


class RagPackValidator:
    """Validates RAG packs against the open specification."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Heuristic estimation of token count (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text.strip()) // 4)

    @classmethod
    def load(cls, file_path: str) -> RagPack:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Pack file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValidationError(f"Root YAML document must be a dictionary in {file_path}")

        cls.validate_dict(data, file_path)
        return cls._build_rag_pack(data)

    @classmethod
    def validate_dict(cls, data: Dict[str, Any], source_ref: str = "<memory>") -> None:
        # 1. Check required root fields
        missing = REQUIRED_ROOT_KEYS - set(data.keys())
        if missing:
            raise ValidationError(f"Missing required root fields in {source_ref}: {sorted(list(missing))}")

        # 2. Check coverage contract
        coverage = data.get("coverage", {})
        if not isinstance(coverage, dict):
            raise ValidationError(f"'coverage' must be a dictionary in {source_ref}")

        covered = coverage.get("covered_topics")
        if not covered or not isinstance(covered, list):
            raise ValidationError(f"'coverage.covered_topics' must be a non-empty list in {source_ref}")

        uncovered = coverage.get("known_uncovered_topics")
        if uncovered is None or not isinstance(uncovered, list):
            raise ValidationError(f"'coverage.known_uncovered_topics' must be a list in {source_ref}")

        # 3. Check authority entries: 'statutes', 'standards', or 'clauses'
        entries_raw = data.get("statutes") or data.get("standards") or data.get("clauses")
        if not entries_raw or not isinstance(entries_raw, list):
            raise ValidationError(
                f"RAG pack must define either a non-empty 'statutes', 'standards', or 'clauses' list in {source_ref}"
            )

        citations_seen: Set[str] = set()

        for idx, entry in enumerate(entries_raw):
            if not isinstance(entry, dict):
                raise ValidationError(f"Entry #{idx} in {source_ref} must be a dictionary")

            citation = entry.get("citation") or entry.get("standard_id") or entry.get("clause_id")
            if not citation:
                raise ValidationError(f"Entry #{idx} in {source_ref} missing citation/standard_id/clause_id")

            if citation in citations_seen:
                raise ValidationError(f"Duplicate citation '{citation}' in {source_ref}")
            citations_seen.add(citation)

            topic = entry.get("topic")
            if not topic:
                raise ValidationError(f"Entry '{citation}' in {source_ref} missing required 'topic'")

            raw_content = entry.get("raw_content", "")
            if not raw_content.strip():
                raise ValidationError(f"Entry '{citation}' in {source_ref} has empty 'raw_content'")

            token_count = cls.estimate_tokens(raw_content)
            if token_count > MAX_CHUNK_TOKEN_BUDGET:
                raise ValidationError(
                    f"Entry '{citation}' exceeds maximum token budget ({token_count} > {MAX_CHUNK_TOKEN_BUDGET} tokens)"
                )

            # Check slots if present
            slots = entry.get("statutory_slots", {})
            if slots and not isinstance(slots, dict):
                raise ValidationError(f"statutory_slots for '{citation}' must be a dictionary")

    @classmethod
    def _build_rag_pack(cls, data: Dict[str, Any]) -> RagPack:
        coverage = data.get("coverage", {})
        entries_raw = data.get("statutes") or data.get("standards") or data.get("clauses") or []

        entries: List[AuthorityEntry] = []
        for e in entries_raw:
            citation = e.get("citation") or e.get("standard_id") or e.get("clause_id") or "unknown"
            raw_content = e.get("raw_content", "")
            token_count = cls.estimate_tokens(raw_content)

            entries.append(
                AuthorityEntry(
                    citation=citation,
                    title=e.get("title", citation),
                    topic=e.get("topic", "General"),
                    authority_class=e.get("authority_class", "statute"),
                    raw_content=raw_content,
                    slots=e.get("statutory_slots", {}),
                    preempts=e.get("preempts", []),
                    preempted_by=e.get("preempted_by", []),
                    exceptions_ref=e.get("exceptions_ref"),
                    defines_terms=e.get("defines_terms", []),
                    estimated_tokens=token_count,
                )
            )

        return RagPack(
            pack_id=data["pack_id"],
            version=str(data["version"]),
            publisher=data["publisher"],
            description=data["description"],
            domain=data.get("domain"),
            state=data.get("state"),
            municipality=data.get("municipality"),
            county=data.get("county"),
            covered_topics=coverage.get("covered_topics", []),
            known_uncovered_topics=coverage.get("known_uncovered_topics", []),
            entries=entries,
            raw_dict=data,
        )


def main():
    parser = argparse.ArgumentParser(description="Validate and inspect RAG Packs.")
    subparsers = parser.add_subparsers(dest="command")

    val_parser = subparsers.add_parser("validate", help="Validate one or more RAG Pack YAML files.")
    val_parser.add_argument("paths", nargs="+", help="File paths or globs to validate.")

    info_parser = subparsers.add_parser("info", help="Inspect a RAG Pack.")
    info_parser.add_argument("path", help="File path to inspect.")

    args = parser.parse_args()

    if args.command == "validate":
        total_files = 0
        failed = 0
        for pattern in args.paths:
            for filepath in glob.glob(pattern, recursive=True):
                total_files += 1
                try:
                    pack = RagPackValidator.load(filepath)
                    print(f"✅ {filepath} — [PASS] Pack ID: {pack.pack_id} ({len(pack.entries)} entries, ~{pack.total_estimated_tokens()} tokens)")
                except Exception as err:
                    failed += 1
                    print(f"❌ {filepath} — [FAIL] {err}", file=sys.stderr)

        if failed > 0:
            print(f"\nValidation failed: {failed}/{total_files} packs invalid.")
            sys.exit(1)
        else:
            print(f"\nAll {total_files} packs validated successfully!")

    elif args.command == "info":
        try:
            pack = RagPackValidator.load(args.path)
            print(f"📦 Pack ID:        {pack.pack_id} (v{pack.version})")
            print(f"🏛️ Publisher:      {pack.publisher}")
            if pack.municipality:
                print(f"📍 Jurisdiction:   {pack.municipality}, {pack.state} ({pack.county})")
            elif pack.domain:
                print(f"🏢 Domain:         {pack.domain}")
            print(f"📝 Description:    {pack.description}")
            print(f"🎯 Topics Covered: {', '.join(pack.covered_topics)}")
            print(f"🚫 Uncovered:      {', '.join(pack.known_uncovered_topics)}")
            print(f"\n--- Authorities / Standards ({len(pack.entries)}) ---")
            for e in pack.entries:
                print(f"  • {e.citation} [{e.topic}] (~{e.estimated_tokens} tokens)")
                if e.slots:
                    for sk, sv in e.slots.items():
                        print(f"      - {sk}: {sv}")
        except Exception as err:
            print(f"❌ Error: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
