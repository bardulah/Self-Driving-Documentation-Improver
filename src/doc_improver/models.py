"""Core data models for the documentation improver."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TargetType(str, Enum):
    """Type of target to explore and document."""
    CODE = "code"
    WEBSITE = "website"
    API = "api"
    MIXED = "mixed"


class ExplorationMode(str, Enum):
    """Exploration thoroughness level."""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class DocumentationType(str, Enum):
    """Type of documentation gap identified."""
    MISSING_DOCSTRING = "missing_docstring"
    INCOMPLETE_DOCSTRING = "incomplete_docstring"
    MISSING_README = "missing_readme"
    MISSING_API_DOCS = "missing_api_docs"
    MISSING_EXAMPLES = "missing_examples"
    OUTDATED_DOCS = "outdated_docs"
    MISSING_INSTALLATION = "missing_installation"
    MISSING_USAGE = "missing_usage"
    MISSING_PARAMETERS = "missing_parameters"
    MISSING_RETURNS = "missing_returns"
    MISSING_EXCEPTIONS = "missing_exceptions"
    UNCLEAR_DESCRIPTION = "unclear_description"


class Severity(str, Enum):
    """Severity level of documentation gap."""
    CRITICAL = "critical"  # Public API without docs
    HIGH = "high"         # Important functions missing docs
    MEDIUM = "medium"     # Standard functions missing docs
    LOW = "low"           # Internal/minor functions missing docs


class CodeEntity(BaseModel):
    """Represents a code entity (function, class, module)."""
    name: str
    type: str  # function, class, method, module
    file_path: str
    line_number: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    is_public: bool = True
    complexity: Optional[int] = None  # Cyclomatic complexity
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None  # Additional context (body, raises, etc.)


class WebPage(BaseModel):
    """Represents a discovered web page."""
    url: str
    title: Optional[str] = None
    content: str = ""
    links: List[str] = Field(default_factory=list)
    has_docs: bool = False
    doc_completeness_score: float = 0.0


class DocumentationGap(BaseModel):
    """Represents an identified documentation gap."""
    id: str
    gap_type: DocumentationType
    severity: Severity
    location: str  # file path or URL
    entity: Optional[CodeEntity] = None
    description: str
    current_documentation: Optional[str] = None
    suggested_improvement: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class DocumentationImprovement(BaseModel):
    """Represents a generated documentation improvement."""
    gap_id: str
    gap: DocumentationGap
    improved_documentation: str
    diff: Optional[str] = None
    confidence_score: float
    reasoning: str


class ExplorationConfig(BaseModel):
    """Configuration for exploration process."""
    target_type: TargetType
    target_path_or_url: str
    mode: ExplorationMode = ExplorationMode.STANDARD
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/.git/**",
        "**/venv/**",
        "**/env/**",
        "**/*.pyc",
        "**/build/**",
        "**/dist/**",
    ])
    include_patterns: List[str] = Field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts", "**/*.md"])
    max_depth: int = 10
    follow_links: bool = True
    analyze_comments: bool = True
    check_examples: bool = True


class GenerationConfig(BaseModel):
    """Configuration for documentation generation."""
    api_key: Optional[str] = None
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.3
    max_tokens: int = 4000
    style: str = "google"  # google, numpy, sphinx
    include_examples: bool = True
    include_type_hints: bool = True
    auto_apply: bool = False  # Automatically apply improvements


class ProjectReport(BaseModel):
    """Complete analysis report for a project."""
    target: str
    target_type: TargetType
    exploration_time: float
    total_entities: int
    gaps_found: List[DocumentationGap]
    improvements_generated: List[DocumentationImprovement]
    coverage_stats: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
