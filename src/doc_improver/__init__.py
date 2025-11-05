"""
Self-Driving Documentation Improver

A sophisticated tool that automatically explores your software or website,
identifies gaps in documentation, and generates documentation improvements
independently using Claude Code and browser automation.
"""

__version__ = "0.1.0"
__author__ = "Documentation Improver Team"

from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.explorer.code_explorer import CodeExplorer
from doc_improver.explorer.web_explorer import WebExplorer
from doc_improver.generator.doc_generator import DocumentationGenerator
from doc_improver.integrations.claude_client import ClaudeClient

__all__ = [
    "CodeExplorer",
    "WebExplorer",
    "GapDetector",
    "DocumentationGenerator",
    "ClaudeClient",
]
