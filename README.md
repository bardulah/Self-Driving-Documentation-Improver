# Self-Driving-Documentation-Improver

A sophisticated tool that automatically explores your software or website, identifies gaps in documentation, and generates documentation improvements independently using Claude AI and browser automation.

## Features

- **Automated Code Exploration**: Analyzes Python, JavaScript, and TypeScript codebases to identify undocumented or poorly documented code
- **Web Documentation Analysis**: Crawls websites using browser automation to find documentation gaps and inconsistencies
- **AI-Powered Documentation Generation**: Uses Claude AI to generate high-quality, context-aware documentation improvements
- **Multiple Documentation Styles**: Supports Google, NumPy, and Sphinx documentation styles
- **Gap Detection**: Sophisticated algorithm to detect missing docstrings, incomplete parameter documentation, missing examples, and more
- **Confidence Scoring**: Assigns confidence scores to generated documentation for safe automatic application
- **Diff Preview**: Shows exactly what will change before applying improvements
- **Batch Processing**: Process multiple gaps efficiently with progress tracking
- **Rich CLI Interface**: Beautiful command-line interface with tables, progress bars, and colored output

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Anthropic API key (for Claude AI)

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/Self-Driving-Documentation-Improver.git
cd Self-Driving-Documentation-Improver

# Install dependencies
pip install -r requirements.txt

# For browser automation support
playwright install

# Install in development mode
pip install -e .
```

## Quick Start

### 1. Set up your API key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 2. Analyze your code

```bash
# Analyze a Python project
doc-improver analyze ./my_project --type code

# Analyze a website
doc-improver analyze https://example.com/docs --type website
```

### 3. Review and apply improvements

```bash
# Preview improvements without applying
doc-improver analyze ./my_project --type code --dry-run

# Apply improvements automatically (high confidence only)
doc-improver analyze ./my_project --type code --apply

# Export detailed report
doc-improver analyze ./my_project --type code -o improvements.md
```

## Usage

### Basic Commands

#### Initialize Configuration

Create a configuration file with sensible defaults:

```bash
doc-improver init
```

This creates `.doc-improver.yaml` in your current directory.

#### Analyze Code

```bash
doc-improver analyze <target> --type code [options]
```

Options:
- `--mode`: Exploration thoroughness (`quick`, `standard`, `deep`)
- `--output, -o`: Export report to file
- `--apply`: Automatically apply improvements
- `--dry-run`: Preview changes without modifying files (default)
- `--config`: Path to configuration file
- `--verbose, -v`: Enable verbose logging

Examples:

```bash
# Quick analysis
doc-improver analyze ./src --type code --mode quick

# Deep analysis with report export
doc-improver analyze ./src --type code --mode deep -o report.md

# Apply improvements automatically
doc-improver analyze ./src --type code --apply
```

#### Analyze Website

```bash
doc-improver analyze <url> --type website [options]
```

Example:

```bash
doc-improver analyze https://myproject.readthedocs.io --type website
```

#### Validate API Key

```bash
doc-improver validate --api-key YOUR_API_KEY
```

### Configuration

Create a `.doc-improver.yaml` file to customize behavior:

```yaml
exploration:
  mode: standard
  max_depth: 10
  follow_links: true
  exclude_patterns:
    - "**/__pycache__/**"
    - "**/node_modules/**"
    - "**/.git/**"

generation:
  model: claude-3-5-sonnet-20241022
  temperature: 0.3
  style: google  # google, numpy, or sphinx
  include_examples: true
  include_type_hints: true
  auto_apply: false
```

See `config/example-config.yaml` for a complete configuration example.

## How It Works

### 1. Exploration Phase

The tool explores your target (code or website) to discover all documentable entities:

- **Code**: Uses AST parsing for Python and regex-based analysis for JavaScript/TypeScript
- **Website**: Uses Playwright for browser automation to crawl pages

### 2. Gap Detection

Analyzes discovered entities to identify documentation gaps:

- Missing docstrings
- Incomplete parameter documentation
- Missing return value documentation
- Missing exception documentation
- Missing usage examples
- Unclear or too-brief descriptions

Each gap is assigned a severity level (Critical, High, Medium, Low) based on:
- Whether the entity is public API
- Complexity of the entity
- Presence of parameters/return values

### 3. Documentation Generation

For each gap, Claude AI generates improved documentation:

- Analyzes code context and signatures
- Follows specified documentation style
- Includes type hints and examples
- Provides reasoning for improvements

### 4. Confidence Scoring

Each improvement receives a confidence score (0-1) based on:

- Documentation length and completeness
- Presence of required sections (Args, Returns, etc.)
- Quality indicators

### 5. Application

Improvements can be:
- Previewed with diff output
- Exported to a report file
- Automatically applied to source files (high confidence only)

## Architecture

```
src/doc_improver/
├── explorer/           # Code and web exploration modules
│   ├── code_explorer.py    # AST-based code analysis
│   └── web_explorer.py     # Browser automation for websites
├── analyzer/           # Gap detection and analysis
│   └── gap_detector.py     # Documentation gap identification
├── generator/          # Documentation generation
│   └── doc_generator.py    # AI-powered improvement generation
├── integrations/       # External service integrations
│   └── claude_client.py    # Claude AI API client
├── cli/               # Command-line interface
│   └── main.py            # CLI commands and UI
├── utils/             # Utilities and helpers
│   ├── config_manager.py   # Configuration handling
│   └── logger.py          # Logging and output
└── models.py          # Core data models
```

## Examples

### Example 1: Analyze Python Package

```bash
doc-improver analyze ./my_package --type code --mode deep -o report.md
```

This will:
1. Recursively explore all Python files in `my_package`
2. Identify all functions, classes, and methods
3. Detect missing or incomplete documentation
4. Generate improvements using Claude AI
5. Export a detailed report to `report.md`

### Example 2: Improve API Documentation

```bash
doc-improver analyze https://api.example.com/docs --type website --mode standard
```

This will:
1. Crawl the API documentation website
2. Analyze documentation completeness
3. Identify pages with missing or incomplete docs
4. Generate suggested improvements

### Example 3: Automatic Improvement Application

```bash
doc-improver analyze ./src --type code --apply --config .doc-improver.yaml
```

This will:
1. Load configuration from `.doc-improver.yaml`
2. Analyze code in `./src`
3. Generate improvements
4. Automatically apply high-confidence improvements
5. Display summary of changes

## Documentation Styles

### Google Style (Default)

```python
def function(param1, param2):
    """Summary line.

    Detailed description.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When validation fails

    Example:
        >>> result = function(1, 2)
        >>> print(result)
    """
```

### NumPy Style

```python
def function(param1, param2):
    """
    Summary line.

    Parameters
    ----------
    param1 : type
        Description
    param2 : type
        Description

    Returns
    -------
    type
        Description
    """
```

### Sphinx Style

```python
def function(param1, param2):
    """
    Summary line.

    :param param1: Description
    :type param1: type
    :param param2: Description
    :type param2: type
    :return: Description
    :rtype: type
    """
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=doc_improver --cov-report=html
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Troubleshooting

### Playwright Installation Issues

If you encounter issues with browser automation:

```bash
playwright install chromium
```

### API Key Issues

Ensure your API key is set correctly:

```bash
echo $ANTHROPIC_API_KEY
```

Or pass it directly:

```bash
doc-improver analyze ./src --type code --api-key YOUR_KEY
```

### Import Errors

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

## Limitations

- JavaScript/TypeScript analysis is regex-based (less accurate than Python AST parsing)
- Web exploration is limited to the same domain by default
- Large codebases may take significant time to process
- API key required for documentation generation

## Future Enhancements

- Support for more programming languages (Java, Go, Rust, etc.)
- Integration with git for automatic PR creation
- Support for API documentation formats (OpenAPI, GraphQL)
- Machine learning-based confidence scoring
- Interactive review mode
- VS Code extension
- CI/CD integration

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [Claude AI](https://www.anthropic.com/claude) by Anthropic
- Uses [Playwright](https://playwright.dev/) for browser automation
- CLI built with [Click](https://click.palletsprojects.com/) and [Rich](https://rich.readthedocs.io/)

## Support

For issues, questions, or contributions, please visit the GitHub repository.

---

Made with care by the Documentation Improver Team
