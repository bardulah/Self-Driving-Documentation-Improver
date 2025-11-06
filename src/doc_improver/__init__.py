"""
Self-Driving Documentation Improver

A sophisticated tool that automatically explores your software or website,
identifies gaps in documentation, and generates documentation improvements
independently using Claude AI and browser automation.

Version 2.0 includes:
- Plugin system for language analyzers
- Async batch processing for faster generation
- Caching layer for API calls and file analysis
- Incremental processing with state management
- Interactive review mode
- Git integration and PR creation
- Metrics and analytics tracking
- Proper AST rewriting with libcst
"""

__version__ = "0.2.0"
__author__ = "Documentation Improver Team"

# Core components (v2 with backward compatibility)
from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.explorer.code_explorer_v2 import CodeExplorerV2 as CodeExplorer
from doc_improver.explorer.web_explorer import WebExplorer
from doc_improver.generator.doc_generator import DocumentationGenerator
from doc_improver.integrations.claude_client_v2 import ClaudeClientV2 as ClaudeClient

# Utilities
from doc_improver.utils.cache import CacheManager
from doc_improver.utils.metrics import MetricsTracker, StateManager
from doc_improver.utils.ast_rewriter import ASTRewriter
from doc_improver.utils.git_integration import GitIntegration

# Plugin system
from doc_improver.explorer.base_analyzer import BaseLanguageAnalyzer, AnalyzerRegistry
from doc_improver.explorer.python_analyzer import PythonAnalyzer
from doc_improver.explorer.javascript_analyzer import JavaScriptAnalyzer

__all__ = [
    # Core
    "CodeExplorer",
    "WebExplorer",
    "GapDetector",
    "DocumentationGenerator",
    "ClaudeClient",
    # Utilities
    "CacheManager",
    "MetricsTracker",
    "StateManager",
    "ASTRewriter",
    "GitIntegration",
    # Plugins
    "BaseLanguageAnalyzer",
    "AnalyzerRegistry",
    "PythonAnalyzer",
    "JavaScriptAnalyzer",
]
