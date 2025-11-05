"""Tests for gap detector."""

import pytest

from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.models import (
    CodeEntity,
    DocumentationType,
    Severity,
)


def test_gap_detector_initialization():
    """Test that gap detector initializes correctly."""
    detector = GapDetector()
    assert len(detector.gaps) == 0


def test_missing_docstring_detection():
    """Test detection of missing docstrings."""
    detector = GapDetector()

    entity = CodeEntity(
        name="test_function",
        type="function",
        file_path="test.py",
        line_number=10,
        docstring=None,
        is_public=True
    )

    gaps = detector.analyze_code_entities([entity])

    assert len(gaps) == 1
    assert gaps[0].gap_type == DocumentationType.MISSING_DOCSTRING
    assert gaps[0].severity == Severity.CRITICAL


def test_private_entity_skipped():
    """Test that private entities are skipped."""
    detector = GapDetector()

    entity = CodeEntity(
        name="_private_function",
        type="function",
        file_path="test.py",
        line_number=10,
        docstring=None,
        is_public=False
    )

    gaps = detector.analyze_code_entities([entity])

    assert len(gaps) == 0


def test_incomplete_docstring_detection():
    """Test detection of incomplete docstrings."""
    detector = GapDetector()

    entity = CodeEntity(
        name="test_function",
        type="function",
        file_path="test.py",
        line_number=10,
        docstring="Does something.",
        is_public=True,
        parameters=[{"name": "arg1"}, {"name": "arg2"}],
        return_type="str"
    )

    gaps = detector.analyze_code_entities([entity])

    # Should detect missing parameter and return documentation
    assert len(gaps) >= 2
    gap_types = [gap.gap_type for gap in gaps]
    assert DocumentationType.MISSING_PARAMETERS in gap_types
    assert DocumentationType.MISSING_RETURNS in gap_types
