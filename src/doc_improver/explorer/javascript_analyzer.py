"""JavaScript/TypeScript analyzer using tree-sitter."""

from pathlib import Path
from typing import List, Optional, Set
import logging

try:
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Node = None

from doc_improver.models import CodeEntity
from doc_improver.explorer.base_analyzer import BaseLanguageAnalyzer
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class JavaScriptAnalyzer(BaseLanguageAnalyzer):
    """Analyzer for JavaScript/TypeScript using tree-sitter."""

    def __init__(self):
        """Initialize JavaScript analyzer."""
        super().__init__()
        self.supported_extensions = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
        self.parser = None
        self._initialize_parser()

    def _initialize_parser(self) -> None:
        """Initialize tree-sitter parser."""
        if not TREE_SITTER_AVAILABLE:
            logger.warning("tree-sitter not available, falling back to regex analysis")
            return

        try:
            # Note: In production, you'd build the language library first
            # For now, we'll use a fallback regex-based approach if tree-sitter fails
            self.parser = Parser()
            # This would need the compiled language library
            # Language.build_library('build/languages.so', ['tree-sitter-javascript'])
            # js_lang = Language('build/languages.so', 'javascript')
            # self.parser.set_language(js_lang)
        except Exception as e:
            logger.warning(f"Could not initialize tree-sitter parser: {e}")
            self.parser = None

    def can_analyze(self, file_path: Path) -> bool:
        """Check if this is a JavaScript/TypeScript file.

        Args:
            file_path: Path to check

        Returns:
            True if JS/TS file
        """
        return file_path.suffix in self.supported_extensions

    def analyze_file(self, file_path: Path, root_path: Path) -> List[CodeEntity]:
        """Analyze a JavaScript/TypeScript file.

        Args:
            file_path: Path to JS/TS file
            root_path: Project root path

        Returns:
            List of code entities
        """
        if self.parser is not None:
            return self._analyze_with_tree_sitter(file_path, root_path)
        else:
            return self._analyze_with_regex(file_path, root_path)

    def _analyze_with_tree_sitter(
        self,
        file_path: Path,
        root_path: Path
    ) -> List[CodeEntity]:
        """Analyze using tree-sitter (more accurate).

        Args:
            file_path: Path to file
            root_path: Project root

        Returns:
            List of code entities
        """
        entities = []

        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            tree = self.parser.parse(content)
            relative_path = str(file_path.relative_to(root_path))

            # Walk the AST
            self._walk_tree(tree.root_node, file_path, relative_path, entities, content)

        except Exception as e:
            logger.error(f"Error analyzing {file_path} with tree-sitter: {e}")

        return entities

    def _walk_tree(
        self,
        node: 'Node',
        file_path: Path,
        relative_path: str,
        entities: List[CodeEntity],
        content: bytes
    ) -> None:
        """Recursively walk tree-sitter AST.

        Args:
            node: Current AST node
            file_path: File path
            relative_path: Relative path
            entities: List to append entities to
            content: File content bytes
        """
        if node.type == 'function_declaration':
            entity = self._extract_function_from_node(node, file_path, relative_path, content)
            if entity:
                entities.append(entity)

        elif node.type == 'class_declaration':
            entity = self._extract_class_from_node(node, file_path, relative_path, content)
            if entity:
                entities.append(entity)

        elif node.type in ['arrow_function', 'function_expression']:
            # Check if this is a named export
            entity = self._extract_arrow_function(node, file_path, relative_path, content)
            if entity:
                entities.append(entity)

        # Recurse into children
        for child in node.children:
            self._walk_tree(child, file_path, relative_path, entities, content)

    def _extract_function_from_node(
        self,
        node: 'Node',
        file_path: Path,
        relative_path: str,
        content: bytes
    ) -> Optional[CodeEntity]:
        """Extract function from tree-sitter node.

        Args:
            node: Function node
            file_path: File path
            relative_path: Relative path
            content: File content

        Returns:
            Code entity or None
        """
        # Get function name
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None

        name = content[name_node.start_byte:name_node.end_byte].decode('utf-8')

        # Get parameters
        params_node = node.child_by_field_name('parameters')
        parameters = []
        if params_node:
            for param in params_node.named_children:
                param_name = content[param.start_byte:param.end_byte].decode('utf-8')
                parameters.append({"name": param_name})

        # Get docstring (JSDoc comment before function)
        docstring = self._extract_jsdoc(node, content)

        # Get function body
        body = self.get_function_body(file_path, node.start_point[0] + 1, max_lines=30)

        return CodeEntity(
            name=name,
            type="function",
            file_path=relative_path,
            line_number=node.start_point[0] + 1,
            signature=content[node.start_byte:node.end_byte].decode('utf-8').split('\n')[0],
            docstring=docstring,
            is_public=not name.startswith('_'),
            parameters=parameters,
            context={'body': body}
        )

    def _extract_class_from_node(
        self,
        node: 'Node',
        file_path: Path,
        relative_path: str,
        content: bytes
    ) -> Optional[CodeEntity]:
        """Extract class from tree-sitter node.

        Args:
            node: Class node
            file_path: File path
            relative_path: Relative path
            content: File content

        Returns:
            Code entity or None
        """
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None

        name = content[name_node.start_byte:name_node.end_byte].decode('utf-8')
        docstring = self._extract_jsdoc(node, content)
        body = self.get_function_body(file_path, node.start_point[0] + 1, max_lines=20)

        return CodeEntity(
            name=name,
            type="class",
            file_path=relative_path,
            line_number=node.start_point[0] + 1,
            docstring=docstring,
            is_public=not name.startswith('_'),
            context={'body': body}
        )

    def _extract_arrow_function(
        self,
        node: 'Node',
        file_path: Path,
        relative_path: str,
        content: bytes
    ) -> Optional[CodeEntity]:
        """Extract arrow function if it's exported/named.

        Args:
            node: Arrow function node
            file_path: File path
            relative_path: Relative path
            content: File content

        Returns:
            Code entity or None
        """
        # Check if parent is a variable declaration
        parent = node.parent
        if parent and parent.type == 'variable_declarator':
            name_node = parent.child_by_field_name('name')
            if name_node:
                name = content[name_node.start_byte:name_node.end_byte].decode('utf-8')
                docstring = self._extract_jsdoc(parent.parent, content)
                body = self.get_function_body(file_path, node.start_point[0] + 1, max_lines=30)

                return CodeEntity(
                    name=name,
                    type="function",
                    file_path=relative_path,
                    line_number=node.start_point[0] + 1,
                    signature=content[node.start_byte:node.end_byte].decode('utf-8').split('\n')[0],
                    docstring=docstring,
                    is_public=not name.startswith('_'),
                    context={'body': body}
                )

        return None

    def _extract_jsdoc(self, node: 'Node', content: bytes) -> Optional[str]:
        """Extract JSDoc comment before a node.

        Args:
            node: AST node
            content: File content

        Returns:
            JSDoc text or None
        """
        # Look for comment nodes before this node
        if node.prev_sibling and node.prev_sibling.type == 'comment':
            comment_text = content[
                node.prev_sibling.start_byte:node.prev_sibling.end_byte
            ].decode('utf-8')

            if comment_text.startswith('/**'):
                # Clean up JSDoc
                lines = comment_text.split('\n')
                cleaned = []
                for line in lines:
                    line = line.strip()
                    line = line.lstrip('/*').rstrip('*/')
                    line = line.lstrip('*').strip()
                    if line:
                        cleaned.append(line)
                return '\n'.join(cleaned)

        return None

    def _analyze_with_regex(self, file_path: Path, root_path: Path) -> List[CodeEntity]:
        """Fallback regex-based analysis when tree-sitter unavailable.

        Args:
            file_path: Path to file
            root_path: Project root

        Returns:
            List of code entities
        """
        import re

        entities = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            relative_path = str(file_path.relative_to(root_path))
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
                    docstring = self._extract_jsdoc_regex(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=30)

                    entities.append(CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        context={'body': body}
                    ))

                # Arrow functions
                match = re.search(arrow_func_pattern, line)
                if match:
                    name = match.group(1)
                    docstring = self._extract_jsdoc_regex(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=30)

                    entities.append(CodeEntity(
                        name=name,
                        type="function",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        context={'body': body}
                    ))

                # Classes
                match = re.search(class_pattern, line)
                if match:
                    name = match.group(1)
                    docstring = self._extract_jsdoc_regex(lines, i - 2)
                    body = self.get_function_body(file_path, i, max_lines=20)

                    entities.append(CodeEntity(
                        name=name,
                        type="class",
                        file_path=relative_path,
                        line_number=i,
                        signature=line.strip(),
                        docstring=docstring,
                        is_public=not name.startswith('_'),
                        context={'body': body}
                    ))

        except Exception as e:
            logger.error(f"Error analyzing JavaScript file {file_path}: {e}")

        return entities

    def _extract_jsdoc_regex(self, lines: List[str], start_line: int) -> Optional[str]:
        """Extract JSDoc using regex (fallback method).

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
                continue
            else:
                break

        if doc_lines:
            import re
            doc_text = '\n'.join(doc_lines)
            doc_text = re.sub(r'/\*\*|\*/|\*', '', doc_text)
            return doc_text.strip()

        return None
