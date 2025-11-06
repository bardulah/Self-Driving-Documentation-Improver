

# Migration Guide to v2.0

This guide helps you migrate from v0.1.0 to v2.0 of the Self-Driving Documentation Improver.

## What's New in v2.0

### Major Features

1. **Plugin System** - Extensible language analyzer architecture
2. **Async Batch Processing** - 5-10x faster documentation generation
3. **Caching Layer** - SQLite-based caching for API calls and file analysis
4. **Incremental Processing** - Resume interrupted runs, skip unchanged files
5. **Interactive Review Mode** - Review and approve improvements one by one
6. **Git Integration** - Automated PR creation with GitHub CLI
7. **Metrics & Analytics** - Track improvements over time
8. **Proper AST Rewriting** - Safe code modification with libcst
9. **Enhanced Context** - Function bodies included in AI prompts
10. **Better Error Handling** - Specific exceptions, retry logic, detailed logging

## Breaking Changes

### API Changes

#### CodeExplorer
```python
# v0.1.0
from doc_improver.explorer.code_explorer import CodeExplorer

explorer = CodeExplorer(config)
entities = explorer.explore()

# v2.0 (backward compatible)
from doc_improver import CodeExplorer  # Now imports CodeExplorerV2

explorer = CodeExplorer(config, use_cache=True)  # New parameter
entities = explorer.explore()  # Same interface
```

#### ClaudeClient
```python
# v0.1.0
from doc_improver.integrations.claude_client import ClaudeClient

client = ClaudeClient(config)
doc, reasoning = client.generate_documentation(gap)

# v2.0 (backward compatible)
from doc_improver import ClaudeClient  # Now imports ClaudeClientV2

client = ClaudeClient(config, use_cache=True)  # New parameter

# Sync (same as before)
doc, reasoning = client.generate_documentation(gap)

# Async (new)
doc, reasoning = await client.generate_documentation_async(gap)

# Batch processing (new)
results = await client.batch_generate_async(gaps, max_concurrent=5)
```

### CLI Changes

#### New Commands
```bash
# Setup wizard (new)
doc-improver setup

# View metrics (new)
doc-improver metrics

# Manage cache (new)
doc-improver cache
doc-improver cache --clear

# Validate config (new)
doc-improver check-config
```

#### Enhanced analyze command
```bash
# v0.1.0
doc-improver analyze ./src --type code --apply

# v2.0 (all features available)
doc-improver analyze ./src --type code \
  --interactive \          # New: Interactive review
  --create-pr \           # New: Auto-create GitHub PR
  --resume \              # New: Resume from checkpoint
  --no-cache              # New: Disable caching
```

## New Dependencies

Add these to your environment:
```bash
pip install libcst aiosqlite questionary
```

Or update from requirements:
```bash
pip install -r requirements.txt --upgrade
```

## Configuration Changes

### New Configuration Options

```yaml
# .doc-improver.yaml

exploration:
  # ... existing options ...

  # New: incremental processing
  use_cache: true
  skip_unchanged: true

generation:
  # ... existing options ...

  # New: batch processing
  max_concurrent: 5
  use_cache: true

  # New: git integration
  auto_commit: false
  create_pr: false
```

## Migration Steps

### Step 1: Update Dependencies

```bash
pip install -r requirements.txt --upgrade
playwright install  # If using web exploration
```

### Step 2: Update Imports (Optional)

If you're using the library programmatically:

```python
# Old imports still work (aliased to v2)
from doc_improver import CodeExplorer, ClaudeClient

# But you can use v2 explicitly
from doc_improver.explorer.code_explorer_v2 import CodeExplorerV2
from doc_improver.integrations.claude_client_v2 import ClaudeClientV2
```

### Step 3: Initialize Cache (First Run)

```bash
# Cache will be initialized automatically on first run
# Located at: .doc-improver-cache/

# To clear cache:
doc-improver cache --clear
```

### Step 4: Run Setup Wizard

```bash
doc-improver setup
```

This will:
- Validate your API key
- Create default configuration
- Set up cache directory

### Step 5: Try New Features

```bash
# Interactive review
doc-improver analyze ./src --type code --interactive

# With git integration
doc-improver analyze ./src --type code --create-pr

# View metrics
doc-improver metrics
```

## New Workflows

### Workflow 1: Interactive Review with PR Creation

```bash
# 1. Analyze with interactive review
doc-improver analyze ./my_project --type code --interactive

# 2. Review and approve improvements interactively

# 3. Create PR automatically
doc-improver analyze ./my_project --type code --create-pr
```

### Workflow 2: Incremental Processing

```bash
# First run
doc-improver analyze ./large_project --type code

# Make some code changes...

# Second run (only processes changed files)
doc-improver analyze ./large_project --type code
```

### Workflow 3: Resume from Checkpoint

```bash
# Start long-running analysis
doc-improver analyze ./huge_project --type code

# ^C (interrupted)

# Resume from last checkpoint
doc-improver analyze ./huge_project --type code --resume
```

## Plugin System

### Creating a Custom Language Analyzer

```python
from doc_improver.explorer.base_analyzer import BaseLanguageAnalyzer
from doc_improver import AnalyzerRegistry

class GoAnalyzer(BaseLanguageAnalyzer):
    def __init__(self):
        super().__init__()
        self.supported_extensions = {'.go'}

    def can_analyze(self, file_path):
        return file_path.suffix in self.supported_extensions

    def analyze_file(self, file_path, root_path):
        # Your analysis logic
        entities = []
        # ...
        return entities

# Register it
registry = AnalyzerRegistry()
registry.register(GoAnalyzer())
```

## Performance Improvements

### Before (v0.1.0)
- Sequential API calls
- No caching
- Regex-based JS/TS analysis
- Re-analyzes all files every run

### After (v2.0)
- Concurrent API calls (5-10x faster)
- Smart caching (API responses + file analysis)
- Tree-sitter based JS/TS analysis (where available)
- Incremental processing (skips unchanged files)

**Expected speedup:** 5-10x on repeat runs, 2-3x on first runs

## Caching Behavior

### What Gets Cached?

1. **API Responses** - Cached for 72 hours
2. **File Analysis** - Cached until file changes
3. **Metrics** - Permanent storage

### Cache Location

```
.doc-improver-cache/
├── cache.db          # SQLite cache
└── metrics.db        # Metrics database
```

### Managing Cache

```bash
# View cache stats
doc-improver cache

# Clear all cache
doc-improver cache --clear

# Cache is also accessible via API
from doc_improver import CacheManager

cache = CacheManager()
stats = cache.get_stats()
```

## Metrics & Analytics

### Viewing Metrics

```bash
doc-improver metrics
```

Shows:
- Total runs
- Improvements applied
- Average confidence scores
- Gaps by severity
- Recent runs

### Programmatic Access

```python
from doc_improver import MetricsTracker

tracker = MetricsTracker()
stats = await tracker.get_stats_summary()
trend = await tracker.get_coverage_trend("/my/project")
```

## Troubleshooting

### libcst Not Available

**Symptom:** Improvements can't be applied automatically

**Solution:**
```bash
pip install libcst
```

### questionary Not Available

**Symptom:** Interactive mode doesn't work

**Solution:**
```bash
pip install questionary
```

### tree-sitter Issues

**Symptom:** JS/TS analysis falls back to regex

**Solution:**
```bash
pip install tree-sitter tree-sitter-javascript tree-sitter-python
```

Note: tree-sitter requires compiled language libraries. The tool automatically falls back to regex if unavailable.

### GitHub CLI Not Found

**Symptom:** `--create-pr` fails

**Solution:**
```bash
# Install GitHub CLI
# macOS
brew install gh

# Linux
# See: https://cli.github.com/

# Authenticate
gh auth login
```

## Backward Compatibility

v2.0 maintains backward compatibility with v0.1.0:

- ✅ All v0.1.0 CLI commands work
- ✅ All v0.1.0 API interfaces work
- ✅ Configuration files compatible
- ✅ No breaking changes to core functionality

New features are **opt-in** via:
- New CLI flags
- New API parameters
- New configuration options

## Getting Help

- Documentation: See updated README.md
- Issues: GitHub Issues
- Examples: See `examples/` directory

## Recommended Upgrade Path

1. **Development Environment First**
   ```bash
   pip install -r requirements.txt --upgrade
   doc-improver setup
   doc-improver analyze ./test_project --type code --interactive
   ```

2. **Test on Small Project**
   ```bash
   doc-improver analyze ./small_project --type code
   ```

3. **Use Incremental Processing on Large Projects**
   ```bash
   doc-improver analyze ./large_project --type code
   ```

4. **Integrate into CI/CD**
   ```bash
   doc-improver analyze ./src --type code --apply --create-pr
   ```

Enjoy the new features! 🚀
