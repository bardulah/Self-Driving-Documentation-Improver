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
# Just find gaps (no API needed)
python -c "
from doc_improver import CodeExplorer, GapDetector
from doc_improver.models import ExplorationConfig, TargetType

config = ExplorationConfig(target_type=TargetType.CODE, target_path_or_url='./your_project')
explorer = CodeExplorer(config, use_cache=False)
entities = explorer.explore()

detector = GapDetector()
gaps = detector.analyze_code_entities(entities)

print(f'Found {len(gaps)} documentation gaps')
for gap in gaps[:5]:
    print(f'  - {gap.description}')
"
```

## With Claude AI (Optional)

If you have an Anthropic API key, you can generate documentation:

```bash
export ANTHROPIC_API_KEY='your-key-here'

# CLI will be available in future version
# For now, use the Python API
```

## Project Status: v0.2.0-beta

**What's Tested:**
- ✅ Core imports work
- ✅ Code exploration works (tested on examples/test_project)
- ✅ Gap detection works
- ✅ Can find undocumented code

**What's NOT Fully Tested:**
- ⚠️ AI generation (limited testing)
- ⚠️ Automatic code modification (use with caution)
- ⚠️ Website crawling
- ⚠️ Large codebase performance

## Features

### Core Features (Working)
- **Code Exploration**: Python (AST-based), JavaScript/TypeScript (regex-based)
- **Gap Detection**: 12 types of documentation issues
- **Severity Classification**: Critical, High, Medium, Low
- **Caching**: SQLite-based caching for faster re-runs
- **Metrics**: Track improvements over time

### Advanced Features (Experimental)
- **AI Generation**: Requires Anthropic API key
- **Interactive Review**: Review improvements one-by-one
- **Git Integration**: Create branches and PRs
- **Batch Processing**: Async API calls

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
