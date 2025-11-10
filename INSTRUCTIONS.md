# Instructions for Self-Driving Documentation Improver

This guide provides instructions on how to use the Self-Driving Documentation Improver tool.

## What It Does

This is a powerful command-line tool for developers that automatically finds and fixes gaps in your project's documentation. It uses AI to read your code, understand what it does, and generate high-quality documentation like docstrings and usage examples.

It can:
*   **Analyze a codebase:** It reads your Python, JavaScript, or TypeScript files to find functions or classes that are missing documentation.
*   **Analyze a website:** It can crawl a live documentation website to find pages that are incomplete.
*   **Generate Improvements:** It uses the Claude AI to write the missing documentation for you.
*   **Show a Preview:** It shows you a "diff" of the proposed changes before it modifies any of your files.

## How to Use It

This is a Command-Line Interface (CLI) tool, which means you run it from your terminal within the project you want to document.

### Prerequisites

*   You must be logged into the server where the tool is located.
*   You need an Anthropic API key (for Claude AI) exported as an environment variable: `export ANTHROPIC_API_KEY='your-api-key-here'`. The key is already configured on this server.
*   Navigate to the project directory you want to analyze. For example: `cd /path/to/my/project`

### 1. Analyzing a Codebase

The primary use case is to analyze a local directory of code.

```bash
# Navigate to the tool's directory first
cd /opt/deployment/repos/Self-Driving-Documentation-Improver

# Run the analyzer on a target project directory
doc-improver analyze /path/to/your/project --type code
```

This command will:
1.  Scan all the code in `/path/to/your/project`.
2.  Identify documentation gaps.
3.  Generate suggestions using AI.
4.  Show you a preview of the changes.

### 2. Applying Improvements

By default, the tool only shows you a preview (a "dry run"). To have the tool actually modify your files and add the documentation, you must add the `--apply` flag.

```bash
# Analyze AND apply the changes
doc-improver analyze /path/to/your/project --type code --apply
```
**Warning:** This will modify your source code files directly. It is highly recommended to use this on a project that is under version control (e.g., Git).

### 3. Analyzing a Website

You can also point the tool at a live documentation website to find gaps.

```bash
doc-improver analyze https://your-docs-website.com --type website
```

This will crawl the website and suggest improvements for pages that seem incomplete.

### 4. Exporting a Report

If you don't want to apply changes directly but want to save the suggestions, you can export them to a Markdown file.

```bash
doc-improver analyze /path/to/your/project --type code -o improvements.md
```

This will create an `improvements.md` file in your current directory containing all the AI-generated suggestions.
