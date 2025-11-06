"""Python language analyzer using AST."""

import ast
from pathlib import Path
from typing import List, Optional
import logging

from doc_improver.models import CodeEntity
from doc_improver.explorer.base_analyzer import BaseLanguageAnalyzer
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class PythonAnalyzer(BaseLanguageAnalyzer):
    """Analyzer for Python code using AST."""

    def __init__(self):
        """Initialize Python analyzer."""
        super().__init__()
        self.supported_extensions = {'.py', '.pyw'}

    def can_analyze(self, file_path: Path) -> bool:
        """Check if this is a Python file.

        Args:
            file_path: Path to check

        Returns:
            True if Python file
        """
        return file_path.suffix in self.supported_extensions

    def analyze_file(self, file_path: Path, root_path: Path) -> List[CodeEntity]:
        """Analyze a Python file using AST.

        Args:
            file_path: Path to Python file
            root_path: Project root path

        Returns:
            List of code entities
        """
        entities = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))
            relative_path = str(file_path.relative_to(root_path))

            # Extract module-level docstring
            module_docstring = ast.get_docstring(tree)
            if not module_docstring:
                entities.append(CodeEntity(
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
                    entities.extend(self._extract_class(node, file_path, relative_path))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Only top-level functions (not methods)
                    if self._is_top_level(node, tree):
                        entity = self._extract_function(node, file_path, relative_path, None)
                        if entity:
                            entities.append(entity)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

        return entities

    def _is_top_level(self, node: ast.AST, tree: ast.Module) -> bool:
        """Check if a function is top-level (not a method).

        Args:
            node: AST node to check
            tree: Module AST

        Returns:
            True if top-level function
        """
        for item in tree.body:
            if item is node:
                return True
        return False

    def _extract_class(
        self,
        node: ast.ClassDef,
        file_path: Path,
        relative_path: str
    ) -> List[CodeEntity]:
        """Extract class and its methods.

        Args:
            node: Class AST node
            file_path: File path
            relative_path: Relative file path

        Returns:
            List of entities (class + methods)
        """
        entities = []
        docstring = ast.get_docstring(node)
        is_public = not node.name.startswith('_')

        # Extract class entity
        class_entity = CodeEntity(
            name=node.name,
            type="class",
            file_path=relative_path,
            line_number=node.lineno,
            docstring=docstring,
            is_public=is_public,
            decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)],
        )

        # Add function body context
        class_entity.context = {
            'body': self.get_function_body(file_path, node.lineno, max_lines=20)
        }

        entities.append(class_entity)

        # Extract methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_entity = self._extract_function(item, file_path, relative_path, node.name)
                if method_entity:
                    entities.append(method_entity)

        return entities

    def _extract_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        relative_path: str,
        class_name: Optional[str]
    ) -> Optional[CodeEntity]:
        """Extract function/method information.

        Args:
            node: Function AST node
            file_path: File path
            relative_path: Relative file path
            class_name: Optional parent class name

        Returns:
            Code entity or None
        """
        docstring = ast.get_docstring(node)
        is_public = not node.name.startswith('_')

        # Extract parameters with type hints
        parameters = []
        for arg in node.args.args:
            param_info = {"name": arg.arg}
            if arg.annotation:
                try:
                    param_info["type"] = ast.unparse(arg.annotation)
                except:
                    param_info["type"] = "Any"
            parameters.append(param_info)

        # Extract return type
        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except:
                return_type = "Any"

        # Get function signature
        try:
            signature = ast.unparse(node).split('\n')[0]
        except:
            signature = f"def {node.name}(...)"

        # Determine if function raises exceptions
        raises_exceptions = self._check_raises(node)

        entity_type = "method" if class_name else "function"
        full_name = f"{class_name}.{node.name}" if class_name else node.name

        # Get function body for context
        function_body = self.get_function_body(file_path, node.lineno, max_lines=30)

        entity = CodeEntity(
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
        )

        # Add additional context
        entity.context = {
            'body': function_body,
            'raises': raises_exceptions,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
        }

        return entity

    def _check_raises(self, node: ast.FunctionDef) -> List[str]:
        """Check if function raises exceptions.

        Args:
            node: Function AST node

        Returns:
            List of exception types raised
        """
        exceptions = []

        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    if isinstance(child.exc, ast.Name):
                        exceptions.append(child.exc.id)
                    elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                        exceptions.append(child.exc.func.id)

        return list(set(exceptions))
