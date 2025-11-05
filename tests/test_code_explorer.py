"""Tests for code explorer."""

import pytest
from pathlib import Path

from doc_improver.explorer.code_explorer import CodeExplorer
from doc_improver.models import ExplorationConfig, TargetType


def test_code_explorer_initialization():
    """Test that code explorer initializes correctly."""
    config = ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url="./examples"
    )
    explorer = CodeExplorer(config)

    assert explorer.config == config
    assert explorer.root_path == Path("./examples")
    assert len(explorer.entities) == 0


def test_should_exclude():
    """Test exclusion pattern matching."""
    config = ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url="./examples",
        exclude_patterns=["**/__pycache__/**", "**/test_*.py"]
    )
    explorer = CodeExplorer(config)

    assert explorer._should_exclude(Path("./examples/__pycache__/file.pyc"))
    assert explorer._should_exclude(Path("./examples/test_foo.py"))
    assert not explorer._should_exclude(Path("./examples/main.py"))


def test_should_analyze():
    """Test file analysis decision."""
    config = ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url="./examples"
    )
    explorer = CodeExplorer(config)

    assert explorer._should_analyze(Path("test.py"))
    assert explorer._should_analyze(Path("test.js"))
    assert not explorer._should_analyze(Path("test.txt"))
    assert not explorer._should_analyze(Path("test.md"))
