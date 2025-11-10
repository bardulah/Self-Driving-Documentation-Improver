# Agent Handoff Document: Self-Driving-Documentation-Improver

**Last Updated**: 2025-11-10
**Current Agent**: Gemini

---

## 🎯 1. Current Status

### Project Overview
This is an advanced command-line (CLI) tool that automates the process of improving documentation for software projects. It analyzes code or websites, identifies documentation gaps, and uses AI to generate high-quality docstrings and examples.

### Deployment Status
*   **Status**: ✅ **Ready for CLI Use**
*   **Platform**: VPS (Not deployed as a service)
*   **Note**: This application is a **CLI tool**, not a web service. It is intended to be run on-demand from the command line to analyze a specific codebase.

### Technology Stack
*   **Language**: Python
*   **AI**: Anthropic (Claude) for documentation generation.
*   **Code Analysis**: AST parsing for Python.
*   **Web Analysis**: Playwright for crawling websites.

### Key Files
*   `INSTRUCTIONS.md`: User-facing guide on how to use the CLI tool.
*   `src/doc_improver/cli/main.py`: The main entry point for the command-line application.
*   `requirements.txt`: The list of Python dependencies.

---

## 🚀 2. Recommended Improvements

This section outlines potential future enhancements for the project.

1.  **IDE Integration**: Develop an extension for popular IDEs like VS Code. This would allow developers to trigger the documentation improver directly from their editor, see inline suggestions, and apply them with a single click.
2.  **CI/CD Integration**: Create a GitHub Action or a similar CI/CD pipeline component. This could automatically scan for documentation gaps in new pull requests and either fail the build, post a comment with suggestions, or automatically create a commit with the documentation improvements.
3.  **Support for More Languages**: Expand the code analysis capabilities to support other popular languages like Java, Go, C#, or Rust, moving beyond the current Python/JS/TS support.
4.  **"Dry Run" with PR Creation**: Add a mode that, instead of applying changes locally, automatically creates a new branch and opens a pull request with the proposed documentation changes. This would make the review and approval process seamless for teams.
5.  **Configuration Wizard**: Add an `init` or `configure` command that interactively walks the user through creating the `.doc-improver.yaml` configuration file, making it easier to get started with custom settings.

---

## 🤝 3. Agent Handoff Notes

### How to Work on This Project

*   **Running the Tool**: This is a CLI tool. To run it, navigate to the project directory (`/opt/deployment/repos/Self-Driving-Documentation-Improver`) and execute the `doc-improver` command. Example: `doc-improver analyze /path/to/project --type code`.
*   **Dependencies**: Python dependencies are managed in `requirements.txt`. If you add a new dependency, you will need to install it on the server using `pip install --break-system-packages <package-name>`.
*   **System Dependencies**: This project relies on Playwright, which requires browser binaries to be installed on the system. If you encounter errors related to browser automation, you may need to run `playwright install`.
*   **API Keys**: The tool requires an Anthropic API key to generate documentation. This is configured via the `ANTHROPIC_API_KEY` environment variable.
*   **Updating Documentation**: If you make any user-facing changes to the CLI commands or options, update the `INSTRUCTIONS.md` file. If you make architectural changes, update this `AGENTS.md` file.

### What to Watch Out For

*   **CLI, Not a Web App**: This tool is not a web service and should not be run with `pm2` or any other process manager expecting a long-running application.
*   **AI Costs**: The tool makes calls to the Claude AI API, which is a paid service. Be mindful of the number of calls made, especially when running the tool on large codebases.
*   **File Modifications**: The `--apply` flag will directly modify source code files. Always ensure the target directory is under version control (Git) before using this flag, so changes can be easily reviewed and reverted if necessary.
