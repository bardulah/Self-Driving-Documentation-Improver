# Self-Driving Documentation Improver

A Python tool that finds undocumented code and can generate documentation improvements using Claude AI.

## What It Actually Does

✅ **Works Right Now:**
- Scans Python and JavaScript/TypeScript files
- Finds functions, classes, and methods without docstrings
- Detects incomplete documentation (missing parameters, returns, etc.)
- Shows you what needs documentation
- Can generate improvements using Claude AI (requires API key)

⚠️ **Limitations:**
- Needs Anthropic API key for AI generation
- Automatic code modification requires manual review
- JavaScript/TypeScript analysis is basic (regex-based)
- Best for Python projects

## Quick Start

### 1. Install

```bash
git clone <repo-url>
cd Self-Driving-Documentation-Improver
pip install -e .
```

### 2. Try the Example

```bash
# No API key needed for this
python examples/working_example.py
```

You'll see:
- 7 code entities found
- 7 documentation gaps detected
- Severity classification (Critical, High, Medium, Low)

### 3. Analyze Your Own Code

```bash
# Check setup
doc-improver check

# Basic analysis (no API needed)
doc-improver analyze ./your_project

# Show detailed information
doc-improver analyze ./your_project --verbose

# Show only statistics
doc-improver analyze ./your_project --stats-only

# Filter by severity (only show critical and high)
doc-improver analyze ./your_project --min-severity high

# Output as JSON (for CI/CD)
doc-improver analyze ./your_project --format json

# Filter files
doc-improver analyze ./your_project --include "*.py" --exclude "test_*"
```

## With Claude AI (Optional)

If you have an Anthropic API key, you can generate and apply documentation:

```bash
export ANTHROPIC_API_KEY='your-key-here'

# Preview what would be changed (dry-run mode)
doc-improver analyze ./your_project --apply --dry-run

# Apply improvements (creates backups by default)
doc-improver analyze ./your_project --apply

# Apply improvements without backups
doc-improver analyze ./your_project --apply --no-backup

# Limit number of improvements
doc-improver analyze ./your_project --apply --max-improvements 5
```

## Project Status: v1.0.0-rc

**Fully Working & Tested:**
- ✅ CLI commands (check, analyze, example)
- ✅ Code exploration (Python AST-based, JavaScript regex-based)
- ✅ Gap detection with severity classification
- ✅ Multiple output formats (table, JSON, simple)
- ✅ Filtering (severity, file patterns)
- ✅ Statistics mode
- ✅ Verbose mode with detailed information
- ✅ Dry-run preview

**Working with API Key:**
- ✅ AI documentation generation
- ✅ Automatic file backups
- ✅ AST-based code modification (with libcst)

**Not Fully Tested:**
- ⚠️ Very large codebases (1000+ files)
- ⚠️ Website crawling feature
- ⚠️ Git integration features

## CLI Commands

### `doc-improver check`
Verify your setup and check if everything is configured correctly.

### `doc-improver analyze <path>`
Analyze code for documentation gaps with these options:

**Output Formats:**
- `--format table` (default): Rich table display
- `--format json`: Machine-readable JSON output
- `--format simple`: Plain text for easy parsing

**Filtering:**
- `--min-severity [critical|high|medium|low]`: Only show gaps at or above severity
- `--include "pattern"`: Only analyze files matching pattern (can use multiple times)
- `--exclude "pattern"`: Skip files matching pattern (can use multiple times)

**Display Options:**
- `--verbose, -v`: Show detailed gap information
- `--stats-only`: Show only statistics without detailed gaps

**AI Features (requires API key):**
- `--apply`: Generate and apply improvements
- `--dry-run`: Preview changes without applying
- `--backup / --no-backup`: Control backup creation (default: on)
- `--max-improvements N`: Limit number of improvements to apply

### `doc-improver example`
Run analysis on built-in example project (no API key needed).

## Use Cases

### CI/CD Integration
```bash
# Check documentation quality in CI pipeline
doc-improver analyze ./src --stats-only --format json > docs-report.json

# Fail build if critical gaps exist
doc-improver analyze ./src --min-severity critical --format simple
```

### Code Review Workflow
```bash
# Review only high-priority gaps
doc-improver analyze ./src --min-severity high --verbose

# Preview improvements before committing
doc-improver analyze ./src --apply --dry-run --max-improvements 5
```

### Incremental Improvements
```bash
# Focus on one module at a time
doc-improver analyze ./src --include "auth/*.py"

# Skip test files
doc-improver analyze ./src --exclude "test_*" --exclude "*_test.py"

# Fix only critical issues first
doc-improver analyze ./src --min-severity critical --apply --max-improvements 10
```

### Quick Health Check
```bash
# Get quick overview
doc-improver analyze ./src --stats-only

# Output:
# Total entities analyzed: 150
# Documented: 95 (63.3%)
# Undocumented: 55 (36.7%)
#
# Total documentation gaps: 87
#   CRITICAL: 12
#   HIGH: 23
#   MEDIUM: 34
#   LOW: 18
```

## Features

### Core Features (Working)
- **Code Exploration**: Python (AST-based), JavaScript/TypeScript (regex-based)
- **Gap Detection**: 12 types of documentation issues
- **Severity Classification**: Critical, High, Medium, Low
- **Multiple Output Formats**: Table, JSON, Simple text
- **Filtering**: By severity, file patterns, and more
- **Statistics Mode**: Quick overview of documentation health

### AI Features (Requires API Key)
- **Documentation Generation**: Uses Claude AI to generate improvements
- **Dry-Run Mode**: Preview changes before applying
- **Automatic Backups**: Creates backups before modifying files
- **Batch Processing**: Process multiple improvements efficiently

## Architecture

```
src/doc_improver/
├── explorer/       # Find code entities
│   ├── python_analyzer.py      # AST-based Python analysis
│   └── javascript_analyzer.py  # Regex-based JS/TS analysis
├── analyzer/       # Detect gaps
│   └── gap_detector.py         # Find missing/incomplete docs
├── integrations/   # External services
│   └── claude_client_v2.py     # Claude AI integration
└── utils/          # Helpers
    ├── cache.py               # SQLite caching
    ├── metrics.py             # Track progress
    └── ast_rewriter.py        # Safe code modification (libcst)
```

## Example Output

```
Step 1: Configuring exploration...
  Target: ./examples/test_project
  Mode: STANDARD

Step 2: Exploring code...
  Found 7 code entities

Step 3: Discovered entities:
  add (function) - ✗ Missing docs
  subtract (function) - ✓ Documented
  Calculator (class) - ✗ Missing docs
  ...

Step 4: Detecting documentation gaps...
  Found 7 documentation gaps

Step 5: Gaps by severity:
  CRITICAL: 5 gaps
    - Function 'add' has no docstring
    - Function 'subtract': Parameters are not documented
  HIGH: 2 gaps
    - Method 'Calculator.multiply' has no docstring
    ...

Summary:
  Total entities: 7
  Public entities: 6
  Documented: 1
  Undocumented: 5
  Documentation gaps: 7
```

## Requirements

```
anthropic>=0.25.0      # Claude AI (optional for generation)
pydantic>=2.5.0       # Data validation
libcst>=1.1.0         # Safe AST modification (optional)
rich>=13.0.0          # Pretty terminal output
aiosqlite>=0.19.0     # Async caching
```

## Development Status

This is a **working prototype**. Use it to:
- Find documentation gaps in your code
- Generate documentation with AI assistance
- Learn about your codebase's documentation coverage

**Not recommended for:**
- Fully automated documentation (always review changes)
- Mission-critical production systems (test first!)
- Very large codebases (performance not optimized)

## Contributing

This tool was built as a demonstration project. If you find it useful:
1. Test it on your code
2. Report issues
3. Suggest improvements
4. Submit PRs

## License

MIT License - see LICENSE file

## Acknowledgments

- Built with [Claude AI](https://www.anthropic.com/claude)
- Uses [libcst](https://github.com/Instagram/LibCST) for safe code modification
- CLI powered by [Rich](https://rich.readthedocs.io/)

---

**Note**: This README reflects the **actual tested capabilities** of the tool, not aspirational features. What you see here works and has been tested.
