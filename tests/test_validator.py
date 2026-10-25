"""
Unit tests for src/validator.py (TEST-01).
"""

import glob
import os
from unittest.mock import patch
import pytest

from src.validator import (
    MAX_CHUNK_TOKEN_BUDGET,
    PackIOError,
    PackReadError,
    PackWriteError,
    RagPackValidator,
    ValidationError,
)


def _first_pack_file() -> str:
    pattern = os.path.join(os.path.dirname(__file__), "..", "packs", "**", "*.yaml")
    files = sorted(glob.glob(pattern, recursive=True))
    assert files, "Expected at least one authority pack YAML file"
    return files[0]


def test_validator_loads_valid_pack():
    pack = RagPackValidator.load(_first_pack_file())
    assert pack.pack_id
    assert len(pack.entries) > 0
    assert pack.total_estimated_tokens() > 0


def test_validator_raises_file_not_found_and_pack_read_error(tmp_path):
    missing = str(tmp_path / "does_not_exist.yaml")
    with pytest.raises(FileNotFoundError):
        RagPackValidator.load(missing)

    target = _first_pack_file()
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        with pytest.raises(PackReadError) as exc_info:
            RagPackValidator.load(target)
        assert isinstance(exc_info.value, PackIOError)


def test_pack_write_error_hierarchy():
    raw_io = OSError("ENOSPC")
    err = PackWriteError("Disk full while writing pack", original_error=raw_io)
    assert isinstance(err, PackIOError)
    assert isinstance(err, ValidationError)
    assert not issubclass(PackIOError, OSError)
    assert err.original_error is raw_io


def test_validator_rejects_oversized_chunk():
    bad_data = {
        "pack_id": "test-pack",
        "version": "1.0.0",
        "publisher": "Test",
        "description": "Test pack",
        "coverage": {
            "covered_topics": ["TopicA"],
            "known_uncovered_topics": ["TopicB"],
        },
        "statutes": [
            {
                "citation": "TEST § 1",
                "topic": "TopicA",
                "raw_content": "x" * ((MAX_CHUNK_TOKEN_BUDGET + 50) * 4),
            }
        ],
    }
    with pytest.raises(ValidationError, match="exceeds maximum token budget"):
        RagPackValidator.validate_dict(bad_data)


def test_resolve_yaml_loader_does_not_mutate_module_globals():
    import src.validator as validator_mod

    assert "yaml" not in validator_mod.__dict__
    loader = RagPackValidator._resolve_yaml_loader()
    assert hasattr(loader, "safe_load")
    assert "yaml" not in validator_mod.__dict__


def test_yaml_load_and_dump_errors_wrapped_in_pack_io_errors(tmp_path):
    import yaml
    from src.scaffold import PackScaffolder

    bad_yaml_path = tmp_path / "malformed.yaml"
    bad_yaml_path.write_text("pack_id: [unclosed\n  : invalid:\n", encoding="utf-8")

    with pytest.raises(PackReadError) as read_exc:
        RagPackValidator.load(str(bad_yaml_path))
    assert isinstance(read_exc.value.original_error, yaml.YAMLError)

    valid_pack = {
        "pack_id": "test-pack-yaml-err",
        "version": "1.0.0",
        "publisher": "Test",
        "description": "Test pack",
        "coverage": {
            "covered_topics": ["TopicA"],
            "known_uncovered_topics": ["TopicB"],
        },
        "statutes": [
            {
                "citation": "TEST § 1",
                "topic": "TopicA",
                "raw_content": "Valid statutory content.",
            }
        ],
    }
    out_path = tmp_path / "out_error.yaml"
    with patch("src.scaffold.yaml.dump", side_effect=yaml.YAMLError("Simulated YAML serialization error")):
        with pytest.raises(PackWriteError) as write_exc:
            PackScaffolder.write_pack(valid_pack, str(out_path), overwrite=True)
        assert isinstance(write_exc.value.original_error, yaml.YAMLError)


