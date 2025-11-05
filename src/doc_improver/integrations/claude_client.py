"""Claude AI client for generating documentation improvements."""

import os
from typing import Optional, Dict, Any
import logging

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from doc_improver.models import (
    CodeEntity,
    DocumentationGap,
    DocumentationType,
    GenerationConfig,
)
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class ClaudeClient:
    """Client for interacting with Claude AI API."""

    def __init__(self, config: GenerationConfig):
        """Initialize Claude client.

        Args:
            config: Generation configuration
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic SDK is not installed. Install it with: pip install anthropic"
            )

        self.config = config
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "No API key provided. Set ANTHROPIC_API_KEY environment variable or pass in config"
            )

        self.client = Anthropic(api_key=self.api_key)

    def generate_documentation(
        self,
        gap: DocumentationGap,
        additional_context: Optional[str] = None
    ) -> tuple[str, str]:
        """Generate improved documentation for a gap.

        Args:
            gap: Documentation gap to address
            additional_context: Optional additional context

        Returns:
            Tuple of (improved_documentation, reasoning)
        """
        logger.debug(f"Generating documentation for gap: {gap.id}")

        prompt = self._build_prompt(gap, additional_context)

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            content = response.content[0].text
            documentation, reasoning = self._parse_response(content)

            logger.debug(f"Generated documentation for {gap.location}")
            return documentation, reasoning

        except Exception as e:
            logger.error(f"Error generating documentation: {e}")
            raise

    def _build_prompt(self, gap: DocumentationGap, additional_context: Optional[str]) -> str:
        """Build prompt for Claude based on the gap.

        Args:
            gap: Documentation gap
            additional_context: Optional additional context

        Returns:
            Formatted prompt string
        """
        style_guide = self._get_style_guide()

        prompt_parts = [
            "You are an expert technical writer helping to improve code documentation.",
            f"\nDocumentation Style: {self.config.style}",
            f"\n{style_guide}",
            f"\n\nGap Type: {gap.gap_type.value}",
            f"Severity: {gap.severity.value}",
            f"Location: {gap.location}",
            f"\nDescription: {gap.description}",
        ]

        # Add entity-specific information
        if gap.entity:
            entity = gap.entity
            prompt_parts.extend([
                f"\n\n### Code Entity Information:",
                f"- Type: {entity.type}",
                f"- Name: {entity.name}",
                f"- File: {entity.file_path}:{entity.line_number}",
            ])

            if entity.signature:
                prompt_parts.append(f"- Signature: `{entity.signature}`")

            if entity.parameters:
                prompt_parts.append(f"- Parameters: {len(entity.parameters)} parameter(s)")
                for param in entity.parameters:
                    param_str = f"  - {param['name']}"
                    if 'type' in param:
                        param_str += f": {param['type']}"
                    prompt_parts.append(param_str)

            if entity.return_type:
                prompt_parts.append(f"- Return Type: {entity.return_type}")

            if entity.decorators:
                prompt_parts.append(f"- Decorators: {', '.join(entity.decorators)}")

        # Add current documentation if exists
        if gap.current_documentation:
            prompt_parts.extend([
                f"\n### Current Documentation:",
                f"```\n{gap.current_documentation}\n```"
            ])

        # Add additional context
        if additional_context:
            prompt_parts.extend([
                f"\n### Additional Context:",
                additional_context
            ])

        # Add instructions
        prompt_parts.extend([
            "\n\n### Task:",
            "Generate comprehensive, clear, and helpful documentation for this code element.",
            "Follow these requirements:",
        ])

        if self.config.include_examples:
            prompt_parts.append("- Include practical usage examples where appropriate")

        if self.config.include_type_hints:
            prompt_parts.append("- Clearly document types for parameters and return values")

        prompt_parts.extend([
            "- Be concise but thorough",
            "- Use clear, professional language",
            "- Focus on WHY and WHEN to use this, not just WHAT it does",
            "\n### Output Format:",
            "Provide your response in two sections:",
            "1. DOCUMENTATION: The complete, improved documentation text",
            "2. REASONING: Brief explanation of your improvements",
            "\nUse this format:",
            "```",
            "DOCUMENTATION:",
            "[Your documentation here]",
            "",
            "REASONING:",
            "[Your reasoning here]",
            "```"
        ])

        return "\n".join(prompt_parts)

    def _get_style_guide(self) -> str:
        """Get documentation style guide based on config.

        Returns:
            Style guide text
        """
        if self.config.style == "google":
            return """
Google Style Guide:
- Start with a one-line summary
- Followed by a blank line and detailed description
- Args section for parameters
- Returns section for return value
- Raises section for exceptions
- Example section for usage examples

Example:
\"\"\"
Summary line.

Detailed description goes here.

Args:
    param1: Description of param1
    param2: Description of param2

Returns:
    Description of return value

Raises:
    ValueError: When validation fails

Example:
    >>> result = function(arg1, arg2)
    >>> print(result)
\"\"\"
"""
        elif self.config.style == "numpy":
            return """
NumPy Style Guide:
- Start with a one-line summary
- Followed by detailed description
- Parameters section with type and description
- Returns section with type and description
- Examples section with doctests

Example:
\"\"\"
Summary line.

Detailed description.

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

Examples
--------
>>> result = function(arg1, arg2)
>>> print(result)
\"\"\"
"""
        elif self.config.style == "sphinx":
            return """
Sphinx Style Guide:
- Start with a summary
- Use :param: for parameters
- Use :type: for parameter types
- Use :return: and :rtype: for returns
- Use :raises: for exceptions

Example:
\"\"\"
Summary line.

Detailed description.

:param param1: Description of param1
:type param1: type
:param param2: Description of param2
:type param2: type
:return: Description of return value
:rtype: type
:raises ValueError: When validation fails
\"\"\"
"""
        else:
            return "Use clear and consistent documentation style."

    def _parse_response(self, content: str) -> tuple[str, str]:
        """Parse Claude's response into documentation and reasoning.

        Args:
            content: Response content from Claude

        Returns:
            Tuple of (documentation, reasoning)
        """
        # Try to parse structured response
        doc_marker = "DOCUMENTATION:"
        reasoning_marker = "REASONING:"

        if doc_marker in content and reasoning_marker in content:
            parts = content.split(reasoning_marker)
            doc_part = parts[0].split(doc_marker)[1].strip()
            reasoning_part = parts[1].strip()

            # Clean up code blocks
            doc_part = doc_part.strip('`').strip()
            reasoning_part = reasoning_part.strip('`').strip()

            return doc_part, reasoning_part

        # Fallback: treat entire response as documentation
        return content.strip(), "Generated comprehensive documentation"

    def batch_generate(
        self,
        gaps: list[DocumentationGap],
        max_concurrent: int = 5
    ) -> list[tuple[str, str]]:
        """Generate documentation for multiple gaps.

        Args:
            gaps: List of documentation gaps
            max_concurrent: Maximum concurrent requests

        Returns:
            List of (documentation, reasoning) tuples
        """
        results = []

        for gap in gaps:
            try:
                doc, reasoning = self.generate_documentation(gap)
                results.append((doc, reasoning))
            except Exception as e:
                logger.error(f"Failed to generate for gap {gap.id}: {e}")
                results.append(("", f"Error: {str(e)}"))

        return results

    def validate_api_key(self) -> bool:
        """Validate that the API key is working.

        Returns:
            True if API key is valid
        """
        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=10,
                messages=[
                    {"role": "user", "content": "Hello"}
                ]
            )
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False
