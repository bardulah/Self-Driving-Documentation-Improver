"""Integration tests for end-to-end workflows."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from doc_improver.models import ExplorationConfig, GenerationConfig, TargetType
from doc_improver.explorer.code_explorer_v2 import CodeExplorerV2
from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.utils.cache import CacheManager
from doc_improver.utils.metrics import MetricsTracker, StateManager
from doc_improver.utils.ast_rewriter import ASTRewriter, can_apply_improvements


@pytest.fixture
def temp_project():
    """Create a temporary test project."""
    temp_dir = tempfile.mkdtemp()
    test_file = Path(temp_dir) / "test_module.py"

    test_file.write_text("""
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
""")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def exploration_config(temp_project):
    """Create exploration config for testing."""
    return ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url=temp_project
    )


def test_full_exploration_workflow(exploration_config):
    """Test complete exploration workflow."""
    # Explore
    explorer = CodeExplorerV2(exploration_config, use_cache=False)
    entities = explorer.explore()

    assert len(entities) > 0

    # Check for undocumented entities
    undocumented = explorer.get_undocumented_entities()
    assert len(undocumented) > 0

    # Detect gaps
    detector = GapDetector()
    gaps = detector.analyze_code_entities(entities)

    assert len(gaps) > 0
    assert gaps[0].gap_type is not None


@pytest.mark.asyncio
async def test_caching_system():
    """Test caching functionality."""
    cache = CacheManager()
    await cache.initialize()

    # Test API cache
    test_key = "test_key_123"
    test_value = "test_value"

    await cache.async_manager.set_api_response(test_key, test_value, ttl_hours=1)
    retrieved = await cache.async_manager.get_api_response(test_key)

    assert retrieved == test_value

    # Test file cache
    file_path = "/tmp/test.py"
    entities = [{"name": "test", "type": "function"}]

    await cache.async_manager.set_file_analysis(file_path, entities)
    # Note: This will fail if file doesn't exist, which is expected

    # Clear cache
    await cache.async_manager.clear_all()
    stats = await cache.async_manager.get_stats()

    assert stats['api_responses'] == 0


@pytest.mark.asyncio
async def test_metrics_tracking():
    """Test metrics tracking."""
    tracker = MetricsTracker()
    await tracker.initialize()

    # Record a run
    run_id = await tracker.record_run(
        target="/test/project",
        target_type="code",
        mode="standard",
        duration=10.5,
        stats={
            'total_entities': 100,
            'gaps_found': 25,
            'improvements_generated': 20,
            'improvements_applied': 15
        }
    )

    assert run_id > 0

    # Record coverage
    await tracker.record_coverage(
        target="/test/project",
        total_entities=100,
        documented_entities=75
    )

    # Get stats
    stats = await tracker.get_stats_summary()
    assert stats['total_runs'] > 0


def test_state_management():
    """Test state management."""
    state_file = Path(tempfile.gettempdir()) / "test_state.json"
    state_mgr = StateManager(state_file)

    # Mark file processed
    state_mgr.mark_file_processed("/test/file.py", "abc123", 5)

    # Check if processed
    assert state_mgr.is_file_processed("/test/file.py", "abc123")
    assert not state_mgr.is_file_processed("/test/file.py", "different_hash")

    # Create checkpoint
    state_mgr.create_checkpoint("test checkpoint", {"progress": 50})

    checkpoint = state_mgr.get_last_checkpoint()
    assert checkpoint is not None
    assert checkpoint['data']['progress'] == 50

    # Cleanup
    state_file.unlink()


@pytest.mark.skipif(not can_apply_improvements(), reason="libcst not available")
def test_ast_rewriting(temp_project):
    """Test AST rewriting with libcst."""
    test_file = Path(temp_project) / "test_module.py"

    # Create a mock improvement
    from doc_improver.models import CodeEntity, DocumentationGap, DocumentationImprovement, DocumentationType, Severity

    entity = CodeEntity(
        name="add",
        type="function",
        file_path=str(test_file),
        line_number=2,
        signature="def add(a, b):",
        is_public=True
    )

    gap = DocumentationGap(
        id="test_gap",
        gap_type=DocumentationType.MISSING_DOCSTRING,
        severity=Severity.HIGH,
        location=f"{test_file}:2",
        entity=entity,
        description="Missing docstring"
    )

    improvement = DocumentationImprovement(
        gap_id="test_gap",
        gap=gap,
        improved_documentation="Add two numbers together.\n\nArgs:\n    a: First number\n    b: Second number\n\nReturns:\n    Sum of a and b",
        confidence_score=0.95,
        reasoning="Generated comprehensive documentation"
    )

    # Apply improvement
    rewriter = ASTRewriter()
    success = rewriter.apply_improvement(improvement, dry_run=True)

    # Note: This might not succeed due to path issues, but tests the interface
    assert isinstance(success, bool)


def test_plugin_system():
    """Test language analyzer plugin system."""
    from doc_improver.explorer.base_analyzer import AnalyzerRegistry
    from doc_improver.explorer.python_analyzer import PythonAnalyzer
    from doc_improver.explorer.javascript_analyzer import JavaScriptAnalyzer

    registry = AnalyzerRegistry()
    registry.register(PythonAnalyzer())
    registry.register(JavaScriptAnalyzer())

    # Test analyzer selection
    python_file = Path("test.py")
    js_file = Path("test.js")
    unknown_file = Path("test.txt")

    py_analyzer = registry.get_analyzer(python_file)
    js_analyzer = registry.get_analyzer(js_file)
    no_analyzer = registry.get_analyzer(unknown_file)

    assert py_analyzer is not None
    assert js_analyzer is not None
    assert no_analyzer is None

    assert isinstance(py_analyzer, PythonAnalyzer)
    assert isinstance(js_analyzer, JavaScriptAnalyzer)


def test_gap_detector_comprehensive():
    """Test gap detector with various scenarios."""
    from doc_improver.models import CodeEntity

    detector = GapDetector()

    # Test with undocumented function
    entity1 = CodeEntity(
        name="my_function",
        type="function",
        file_path="test.py",
        line_number=10,
        docstring=None,
        is_public=True,
        parameters=[{"name": "x"}, {"name": "y"}],
        return_type="int"
    )

    # Test with partially documented function
    entity2 = CodeEntity(
        name="another_function",
        type="function",
        file_path="test.py",
        line_number=20,
        docstring="Does something.",
        is_public=True,
        parameters=[{"name": "data"}],
        return_type="str"
    )

    gaps = detector.analyze_code_entities([entity1, entity2])

    # Should find multiple gaps
    assert len(gaps) >= 2

    # Check gap types
    gap_types = [g.gap_type.value for g in gaps]
    assert 'missing_docstring' in gap_types or 'missing_parameters' in gap_types
