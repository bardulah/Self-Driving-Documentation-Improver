"""Code exploration and analysis module."""

import ast
import re
from pathlib import Path
from typing import List, Optional, Set
import logging

from doc_improver.models import CodeEntity, ExplorationConfig
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class CodeExplorer:
    """Explores and analyzes code repositories to extract entities."""

    def __init__(self, config: ExplorationConfig):
        """Initialize code explorer.

        Args:
            config: Exploration configuration
        """
        self.config = config
        self.root_path = Path(config.target_path_or_url)
        self.entities: List[CodeEntity] = []

    def explore(self) -> List[CodeEntity]:
        """Explore the code repository and extract all entities.

        Returns:
            List of discovered code entities
        """
        logger.info(f"Exploring code at: {self.root_path}")

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

        if self.root_path.is_file():
            self._analyze_file(self.root_path)
        else:
            self._explore_directory(self.root_path)

        logger.info(f"Found {len(self.entities)} code entities")
        return self.entities

    def _explore_directory(self, directory: Path, depth: int = 0) -> None:
        """Recursively explore directory for code files.

        Args:
            directory: Directory to explore
            depth: Current recursion depth
        """
        if depth > self.config.max_depth:
            return

        try:
            for item in directory.iterdir():
                # Skip excluded patterns
                if self._should_exclude(item):
                    continue

                if item.is_file() and self._should_analyze(item):
                    self._analyze_file(item)
                elif item.is_dir():
                    self._explore_directory(item, depth + 1)
        except PermissionError:
            logger.warning(f"Permission denied: {directory}")

    def _should_exclude(self, path: Path) -> bool:
        """Check if path matches exclusion patterns.

        Args:
            path: Path to check

        Returns:
            True if should be excluded
        """
        path_str = str(path)
        for pattern in self.config.exclude_patterns:
            if Path(path_str).match(pattern):
                return True
        return False

    def _should_analyze(self, path: Path) -> bool:
        """Check if file should be analyzed.

        Args:
            path: File path to check

        Returns:
            True if should be analyzed
        """
        return path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx']

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single code file.

        Args:
            file_path: Path to the file to analyze
        """
        try:
            if file_path.suffix == '.py':
                self._analyze_python_file(file_path)
            elif file_path.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                self._analyze_javascript_file(file_path)
        except Exception as e:
            logger.warning(f"Error analyzing {file_path}: {e}")

    def _analyze_python_file(self, file_path: Path) -> None:
        """Analyze a Python file using AST.

        Args:
            file_path: Path to Python file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))
            relative_path = str(file_path.relative_to(self.root_path.parent))

            # Extract module-level docstring
            module_docstring = ast.get_docstring(tree)
            if not module_docstring:
                # Module itself needs documentation
                self.entities.append(CodeEntity(
                    name=file_path.stem,
                    type="module",
                    file_path=relative_path,
                    line_number=1,
                    docstring=None,
                    is_public=not file_path.stem.startswith('_'),
                ))

            # Analyze classes and functions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._extract_class(node, file_path, relative_path)
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    self._extract_function(node, file_path, relative_path, None)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")

    def _extract_class(self, node: ast.ClassDef, file_path: Path, relative_path: str) -> None:
        """Extract class information.

        Args:
            node: AST class node
            file_path: File path
            relative_path: Relative file path
        """
        docstring = ast.get_docstring(node)
        is_public = not node.name.startswith('_')

        self.entities.append(CodeEntity(
            name=node.name,
            type="class",
            file_path=relative_path,
            line_number=node.lineno,
            docstring=docstring,
            is_public=is_public,
            decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)],
        ))

        # Extract methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(item, file_path, relative_path, node.name)

    def _extract_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        relative_path: str,
        class_name: Optional[str]
    ) -> None:
        """Extract function/method information.

        Args:
            node: AST function node
            file_path: File path
            relative_path: Relative file path
            class_name: Optional parent class name
        """
        docstring = ast.get_docstring(node)
        is_public = not node.name.startswith('_')

        # Extract parameters
        parameters = []
        for arg in node.args.args:
            param_info = {"name": arg.arg}
            if arg.annotation:
                param_info["type"] = ast.unparse(arg.annotation)
            parameters.append(param_info)

        # Extract return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Get function signature
        try:
            signature = ast.unparse(node).split('\n')[0]
        except:
            signature = f"def {node.name}(...)"

        entity_type = "method" if class_name else "function"
        full_name = f"{class_name}.{node.name}" if class_name else node.name

        self.entities.append(CodeEntity(
            name=full_name,
            type=entity_type,
            file_path=relative_path,
            line_number=node.lineno,
            signature=signature,
            docstring=docstring,
            is_public=is_public,
            parameters=parameters,
            return_type=return_type,
            decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)],
        ))

    def _analyze_javascript_file(self, file_path: Path) -> None:
        """Analyze a JavaScript/TypeScript file (basic regex-based analysis).

        Args:
            file_path: Path to JS/TS file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            relative_path = str(file_path.relative_to(self.root_path.parent))
            lines = content.split('\n')

            # Find function declarations
            func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
            arrow_func_pattern = r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'
            class_pattern = r'(?:export\s+)?class\s+(\w+)'

            for i, line in enumerate(lines, 1):
                # Function declarations
                match = re.search(func_pattern, line)
                if match:
                    name = match.group(1)
                    params = match.group(2)
                    docstring = self._extract_jsdoc(lines, i - 2)

                    self.entities.append(CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                    ))

                # Arrow functions
                match = re.search(arrow_func_pattern, line)
                if match:
                    name = match.group(1)
                    params = match.group(2)
                    docstring = self._extract_jsdoc(lines, i - 2)

                    self.entities.append(CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                    ))

                # Classes
                match = re.search(class_pattern, line)
                if match:
                    name = match.group(1)
                    docstring = self._extract_jsdoc(lines, i - 2)

                    self.entities.append(CodeEntity(
                        name=name,
                        type="class",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                    ))

        except Exception as e:
            logger.warning(f"Error analyzing JavaScript file {file_path}: {e}")

    def _extract_jsdoc(self, lines: List[str], start_line: int) -> Optional[str]:
        """Extract JSDoc comment before a declaration.

        Args:
            lines: File lines
            start_line: Line to start searching backwards from

        Returns:
            JSDoc comment text or None
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
                continue
            else:
                break

        if doc_lines:
            # Clean up JSDoc formatting
            doc_text = '\n'.join(doc_lines)
            doc_text = re.sub(r'/\*\*|\*/|\*', '', doc_text)
            return doc_text.strip()

        return None

    def get_public_entities(self) -> List[CodeEntity]:
        """Get only public entities that should be documented.

        Returns:
            List of public code entities
        """
        return [e for e in self.entities if e.is_public]

    def get_undocumented_entities(self) -> List[CodeEntity]:
        """Get entities without documentation.

        Returns:
            List of undocumented code entities
        """
        return [e for e in self.entities if e.is_public and not e.docstring]
