"""Automated slot extraction utilities for krusch-authority-packs scaffolding."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .scaffold_models import WORD_NUMERALS


class SlotExtractor:
    """Helper utilities to extract candidate slots from raw legal/commercial text."""

    @staticmethod
    def extract_percentages(text: str) -> List[Tuple[float, str]]:
        """Extracts percentages e.g. '50%', '33.0 percent' along with surrounding context."""
        results = []
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", text, re.IGNORECASE):
            val = float(match.group(1))
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((val, context))
        return results

    @staticmethod
    def extract_day_windows(text: str) -> List[Tuple[int, str, str]]:
        """Extracts day intervals e.g. '21 calendar days', '3 business days', '30 days'."""
        results = []
        pattern = r"(\d+)\s+(calendar|business|court)?\s*days?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            days = int(match.group(1))
            day_type = (match.group(2) or "calendar").lower()
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((days, day_type, context))
        return results

    @staticmethod
    def extract_month_windows(text: str) -> List[Tuple[int, str]]:
        """Extracts month intervals e.g. '36 consecutive months', '12 months'."""
        results = []
        pattern = r"(\d+)\s+(?:consecutive\s+)?months?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            months = int(match.group(1))
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((months, context))
        return results

    @staticmethod
    def extract_word_numerals(text: str) -> Dict[str, int]:
        """Detects spelled-out numbers in text."""
        found = {}
        text_lower = text.lower()
        for word, val in sorted(WORD_NUMERALS.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
                found[word] = val
        return found
