"""JavaScript/TypeScript analyzer using regex-based parsing."""

from pathlib import Path
from typing import List, Optional
import re
import logging

from doc_improver.models import CodeEntity
from doc_improver.explorer.base_analyzer import BaseLanguageAnalyzer
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class JavaScriptAnalyzer(BaseLanguageAnalyzer):
    """Analyzer for JavaScript/TypeScript using regex-based parsing.

    Note: This is a simplified analyzer that uses regex patterns.
    For production use with large codebases, consider proper AST parsing.
    """

    def __init__(self):
        """Initialize JavaScript analyzer."""
        super().__init__()
        self.supported_extensions = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    def can_analyze(self, file_path: Path) -> bool:
        """Check if this is a JavaScript/TypeScript file.

        Args:
            file_path: Path to check

        Returns:
            True if JS/TS file
        """
        return file_path.suffix in self.supported_extensions

    def analyze_file(self, file_path: Path, root_path: Path) -> List[CodeEntity]:
        """Analyze a JavaScript/TypeScript file using regex patterns.

        Args:
            file_path: Path to JS/TS file
            root_path: Project root path

        Returns:
            List of code entities
        """
        entities = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            relative_path = str(file_path.relative_to(root_path))
            lines = content.split('\n')

            # Regular expression patterns
            func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
            arrow_func_pattern = r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'
            class_pattern = r'(?:export\s+)?class\s+(\w+)'

            for i, line in enumerate(lines, 1):
                # Function declarations
                match = re.search(func_pattern, line)
                if match:
                    name = match.group(1)
                    params_str = match.group(2)
                    docstring = self._extract_jsdoc(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=30)

                    # Parse parameters
                    parameters = []
                    if params_str.strip():
                        for param in params_str.split(','):
                            param = param.strip()
                            if param:
                                # Handle TypeScript types
                                param_name = param.split(':')[0].strip()
                                parameters.append({"name": param_name})

                    entity = CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        parameters=parameters,
                        context={'body': body} if body else None
                    )
                    entities.append(entity)

                # Arrow functions
                match = re.search(arrow_func_pattern, line)
                if match:
                    name = match.group(1)
                    params_str = match.group(2)
                    docstring = self._extract_jsdoc(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=30)

                    # Parse parameters
                    parameters = []
                    if params_str.strip():
                        for param in params_str.split(','):
                            param = param.strip()
                            if param:
                                param_name = param.split(':')[0].strip()
                                parameters.append({"name": param_name})

                    entity = CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        parameters=parameters,
                        context={'body': body} if body else None
                    )
                    entities.append(entity)

                # Classes
                match = re.search(class_pattern, line)
                if match:
                    name = match.group(1)
                    docstring = self._extract_jsdoc(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=20)

                    entity = CodeEntity(
                        name=name,
                        type="class",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        context={'body': body} if body else None
                    )
                    entities.append(entity)

        except Exception as e:
            logger.error(f"Error analyzing JavaScript file {file_path}: {e}")

        return entities

    def _extract_jsdoc(self, lines: List[str], start_line: int) -> Optional[str]:
        """Extract JSDoc comment before a declaration.

        Args:
            lines: File lines
            start_line: Line to start searching backwards from

        Returns:
            JSDoc text or None
        """
        if start_line < 0 or start_line >= len(lines):
            return None

        doc_lines = []
        for i in range(start_line, -1, -1):
            line = lines[i].strip()

            if line.startswith('*/'):
                doc_lines.insert(0, line)
            elif line.startswith('*'):
                doc_lines.insert(0, line)
            elif line.startswith('/**'):
                doc_lines.insert(0, line)
                break
            elif not line:
                # Skip empty lines
                continue
            else:
                # Hit non-comment line, stop
                break

        if doc_lines and doc_lines[0].startswith('/**'):
            # Clean up JSDoc formatting
            doc_text = '\n'.join(doc_lines)
            # Remove JSDoc markers
            doc_text = re.sub(r'/\*\*|\*/|\* ?', '', doc_text)
            doc_text = doc_text.strip()
            return doc_text if doc_text else None

        return None
