"""AST rewriting utilities using libcst for safe code modification."""

from pathlib import Path
from typing import Optional, Union
import logging

try:
    import libcst as cst
    from libcst import matchers as m
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False
    cst = None

from doc_improver.models import CodeEntity, DocumentationImprovement
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocstringRewriter(cst.CSTTransformer if LIBCST_AVAILABLE else object):
    """CST transformer to add/update docstrings."""

    def __init__(self, entity: CodeEntity, new_docstring: str):
        """Initialize rewriter.

        Args:
            entity: Code entity to update
            new_docstring: New docstring text
        """
        if not LIBCST_AVAILABLE:
            raise ImportError("libcst is required for AST rewriting. Install with: pip install libcst")

        super().__init__()
        self.entity = entity
        self.new_docstring = new_docstring
        self.target_line = entity.line_number
        self.modified = False

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef
    ) -> Union[cst.FunctionDef, cst.RemovalSentinel]:
        """Update function docstrings.

        Args:
            original_node: Original function node
            updated_node: Updated function node

        Returns:
            Modified function node
        """
        # Check if this is the target function by name and line
        if self._is_target_node(original_node, "function"):
            return self._add_or_update_docstring(updated_node)

        return updated_node

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef
    ) -> Union[cst.ClassDef, cst.RemovalSentinel]:
        """Update class docstrings.

        Args:
            original_node: Original class node
            updated_node: Updated class node

        Returns:
            Modified class node
        """
        if self._is_target_node(original_node, "class"):
            return self._add_or_update_docstring(updated_node)

        return updated_node

    def _is_target_node(self, node: Union[cst.FunctionDef, cst.ClassDef], node_type: str) -> bool:
        """Check if this node is the target to modify.

        Args:
            node: CST node
            node_type: Type of node (function/class)

        Returns:
            True if this is the target node
        """
        if self.entity.type != node_type and self.entity.type != "method":
            return False

        # Get node name
        if hasattr(node, 'name'):
            node_name = node.name.value
        else:
            return False

        # Check if name matches (for methods, extract just the method name)
        entity_name = self.entity.name
        if '.' in entity_name:
            entity_name = entity_name.split('.')[-1]

        return node_name == entity_name

    def _add_or_update_docstring(
        self,
        node: Union[cst.FunctionDef, cst.ClassDef]
    ) -> Union[cst.FunctionDef, cst.ClassDef]:
        """Add or update docstring in a node.

        Args:
            node: Function or class node

        Returns:
            Modified node
        """
        # Format docstring as a simple string
        docstring_node = cst.SimpleStatementLine(
            body=[
                cst.Expr(
                    value=cst.SimpleString(
                        value=self._format_docstring(self.new_docstring)
                    )
                )
            ]
        )

        # Get current body
        if isinstance(node.body, cst.IndentedBlock):
            current_body = list(node.body.body)

            # Check if first statement is a docstring
            has_docstring = False
            if current_body:
                first_stmt = current_body[0]
                if isinstance(first_stmt, cst.SimpleStatementLine):
                    if isinstance(first_stmt.body[0], cst.Expr):
                        if isinstance(first_stmt.body[0].value, (cst.SimpleString, cst.ConcatenatedString)):
                            has_docstring = True

            if has_docstring:
                # Replace existing docstring
                current_body[0] = docstring_node
            else:
                # Insert new docstring at beginning
                current_body.insert(0, docstring_node)

            # Create new body
            new_body = node.body.with_changes(body=current_body)
            self.modified = True

            return node.with_changes(body=new_body)

        return node

    def _format_docstring(self, text: str) -> str:
        """Format docstring text for Python.

        Args:
            text: Docstring text

        Returns:
            Properly formatted docstring string
        """
        # Clean and format the text
        text = text.strip()

        # Check if single line or multi-line
        if '\n' not in text:
            # Single line
            return f'"""{text}"""'
        else:
            # Multi-line - ensure proper formatting
            lines = text.split('\n')
            # Remove any existing quotes
            lines = [line.strip('"\'') for line in lines]

            result = ['"""']
            result.extend(lines)
            result.append('"""')
            return '\n'.join(result)


class ASTRewriter:
    """High-level AST rewriting interface."""

    def __init__(self):
        """Initialize AST rewriter."""
        if not LIBCST_AVAILABLE:
            raise ImportError("libcst is required for AST rewriting. Install with: pip install libcst")

    def apply_improvement(
        self,
        improvement: DocumentationImprovement,
        dry_run: bool = False
    ) -> bool:
        """Apply a documentation improvement to source file.

        Args:
            improvement: Improvement to apply
            dry_run: If True, don't actually modify file

        Returns:
            True if successful
        """
        gap = improvement.gap
        if not gap.entity:
            logger.warning(f"Cannot apply improvement without entity: {gap.id}")
            return False

        file_path = Path(gap.entity.file_path)
        if not file_path.exists():
            # Try to find it relative to current directory
            file_path = Path.cwd() / file_path
            if not file_path.exists():
                logger.error(f"File not found: {gap.entity.file_path}")
                return False

        try:
            # Read the source file
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse with libcst
            try:
                tree = cst.parse_module(source_code)
            except cst.ParserSyntaxError as e:
                logger.error(f"Syntax error parsing {file_path}: {e}")
                return False

            # Apply transformation
            rewriter = DocstringRewriter(gap.entity, improvement.improved_documentation)
            modified_tree = tree.visit(rewriter)

            if not rewriter.modified:
                logger.warning(f"No modifications made for {gap.entity.name} in {file_path}")
                return False

            # Get modified code
            modified_code = modified_tree.code

            # Write back if not dry run
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_code)

                logger.info(f"Applied improvement to {file_path}:{gap.entity.line_number}")
            else:
                logger.info(f"[DRY RUN] Would apply improvement to {file_path}:{gap.entity.line_number}")

            return True

        except Exception as e:
            logger.error(f"Error applying improvement to {file_path}: {e}", exc_info=True)
            return False

    def apply_improvements_batch(
        self,
        improvements: list[DocumentationImprovement],
        dry_run: bool = False
    ) -> dict[str, int]:
        """Apply multiple improvements.

        Args:
            improvements: List of improvements
            dry_run: If True, don't actually modify files

        Returns:
            Statistics dictionary
        """
        stats = {
            "total": len(improvements),
            "applied": 0,
            "failed": 0,
            "skipped": 0,
        }

        # Group by file for efficiency
        by_file = {}
        for imp in improvements:
            if imp.gap.entity:
                file_path = imp.gap.entity.file_path
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(imp)

        # Process each file
        for file_path, file_improvements in by_file.items():
            logger.info(f"Processing {len(file_improvements)} improvements for {file_path}")

            for imp in file_improvements:
                # Skip low confidence improvements
                if imp.confidence_score < 0.5:
                    logger.debug(f"Skipping low confidence improvement: {imp.gap.id}")
                    stats["skipped"] += 1
                    continue

                success = self.apply_improvement(imp, dry_run=dry_run)
                if success:
                    stats["applied"] += 1
                else:
                    stats["failed"] += 1

        return stats


def can_apply_improvements() -> bool:
    """Check if AST rewriting is available.

    Returns:
        True if libcst is available
    """
    return LIBCST_AVAILABLE


def get_rewriter() -> Optional[ASTRewriter]:
    """Get an AST rewriter instance if available.

    Returns:
        ASTRewriter or None
    """
    if LIBCST_AVAILABLE:
        return ASTRewriter()
    else:
        logger.warning("libcst not available, cannot apply improvements automatically")
        return None
