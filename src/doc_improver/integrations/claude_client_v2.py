"""Enhanced Claude AI client with async support, caching, and better context."""

import os
import asyncio
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
import logging

try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from doc_improver.models import (
    CodeEntity,
    DocumentationGap,
    DocumentationType,
    GenerationConfig,
)
from doc_improver.utils.cache import CacheManager
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class ClaudeClientV2:
    """Enhanced Claude client with async support and caching."""

    def __init__(self, config: GenerationConfig, use_cache: bool = True):
        """Initialize Claude client.

        Args:
            config: Generation configuration
            use_cache: Whether to use caching
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
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        self.cache = CacheManager() if use_cache else None

    async def generate_documentation_async(
        self,
        gap: DocumentationGap,
        additional_context: Optional[str] = None
    ) -> Tuple[str, str]:
        """Generate improved documentation asynchronously.

        Args:
            gap: Documentation gap to address
            additional_context: Optional additional context

        Returns:
            Tuple of (improved_documentation, reasoning)
        """
        # Check cache first
        cache_key = None
        if self.cache:
            cache_key = self._generate_cache_key(gap)
            cached = await self.cache.async_manager.get_api_response(cache_key)
            if cached:
                logger.debug(f"Using cached response for gap {gap.id}")
                result = json.loads(cached)
                return result['documentation'], result['reasoning']

        # Build prompt with enhanced context
        prompt = self._build_enhanced_prompt(gap, additional_context)

        try:
            response = await self.async_client.messages.create(
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

            # Cache the result
            if self.cache and cache_key:
                result_json = json.dumps({
                    'documentation': documentation,
                    'reasoning': reasoning
                })
                await self.cache.async_manager.set_api_response(
                    cache_key,
                    result_json,
                    ttl_hours=72,
                    metadata={'gap_id': gap.id, 'gap_type': gap.gap_type.value}
                )

            logger.debug(f"Generated documentation for {gap.location}")
            return documentation, reasoning

        except Exception as e:
            logger.error(f"Error generating documentation: {e}", exc_info=True)
            raise

    def generate_documentation(
        self,
        gap: DocumentationGap,
        additional_context: Optional[str] = None
    ) -> Tuple[str, str]:
        """Synchronous wrapper for generate_documentation_async.

        Args:
            gap: Documentation gap to address
            additional_context: Optional additional context

        Returns:
            Tuple of (improved_documentation, reasoning)
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.generate_documentation_async(gap, additional_context)
        )

    async def batch_generate_async(
        self,
        gaps: List[DocumentationGap],
        max_concurrent: int = 5,
        progress_callback: Optional[callable] = None
    ) -> List[Tuple[str, str]]:
        """Generate documentation for multiple gaps concurrently.

        Args:
            gaps: List of documentation gaps
            max_concurrent: Maximum concurrent requests
            progress_callback: Optional callback for progress updates

        Returns:
            List of (documentation, reasoning) tuples
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_gap(gap: DocumentationGap, index: int) -> Tuple[int, Tuple[str, str]]:
            """Process a single gap with semaphore."""
            async with semaphore:
                try:
                    result = await self.generate_documentation_async(gap)
                    if progress_callback:
                        progress_callback(index, len(gaps))
                    return index, result
                except Exception as e:
                    logger.error(f"Failed to generate for gap {gap.id}: {e}")
                    return index, ("", f"Error: {str(e)}")

        # Create tasks for all gaps
        tasks = [process_gap(gap, i) for i, gap in enumerate(gaps)]

        # Wait for all tasks to complete
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        # Sort results by index to maintain order
        sorted_results = sorted(
            [r for r in completed if not isinstance(r, Exception)],
            key=lambda x: x[0]
        )

        return [r[1] for r in sorted_results]

    def batch_generate(
        self,
        gaps: List[DocumentationGap],
        max_concurrent: int = 5
    ) -> List[Tuple[str, str]]:
        """Synchronous wrapper for batch_generate_async.

        Args:
            gaps: List of documentation gaps
            max_concurrent: Maximum concurrent requests

        Returns:
            List of (documentation, reasoning) tuples
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.batch_generate_async(gaps, max_concurrent)
        )

    def _generate_cache_key(self, gap: DocumentationGap) -> str:
        """Generate cache key for a gap.

        Args:
            gap: Documentation gap

        Returns:
            Cache key string
        """
        # Create a unique key based on gap characteristics
        key_parts = [
            gap.gap_type.value,
            gap.location,
            self.config.model,
            str(self.config.temperature),
            self.config.style,
        ]

        if gap.entity:
            key_parts.extend([
                gap.entity.name,
                gap.entity.signature or "",
                str(gap.entity.parameters),
                gap.entity.return_type or "",
            ])

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _build_enhanced_prompt(
        self,
        gap: DocumentationGap,
        additional_context: Optional[str]
    ) -> str:
        """Build enhanced prompt with function body context.

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

        # Add entity-specific information with function body
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
                prompt_parts.append(f"- Parameters ({len(entity.parameters)}):")
                for param in entity.parameters:
                    param_str = f"  - {param['name']}"
                    if 'type' in param:
                        param_str += f": {param['type']}"
                    prompt_parts.append(param_str)

            if entity.return_type:
                prompt_parts.append(f"- Return Type: {entity.return_type}")

            if entity.decorators:
                prompt_parts.append(f"- Decorators: {', '.join(entity.decorators)}")

            # Add function body for context
            if hasattr(entity, 'context') and entity.context:
                if 'body' in entity.context and entity.context['body']:
                    prompt_parts.extend([
                        "\n### Function/Class Implementation:",
                        "```python" if entity.file_path.endswith('.py') else "```javascript",
                        entity.context['body'][:1000],  # Limit to 1000 chars
                        "```"
                    ])

                if 'raises' in entity.context and entity.context['raises']:
                    prompt_parts.append(f"- Raises: {', '.join(entity.context['raises'])}")

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
            "- Base your documentation on the actual implementation provided",
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
"""
        elif self.config.style == "numpy":
            return """
NumPy Style Guide:
- Start with a one-line summary
- Parameters section with type and description
- Returns section with type and description
- Examples section with doctests
"""
        elif self.config.style == "sphinx":
            return """
Sphinx Style Guide:
- Use :param: for parameters
- Use :type: for parameter types
- Use :return: and :rtype: for returns
- Use :raises: for exceptions
"""
        else:
            return "Use clear and consistent documentation style."

    def _parse_response(self, content: str) -> Tuple[str, str]:
        """Parse Claude's response into documentation and reasoning.

        Args:
            content: Response content from Claude

        Returns:
            Tuple of (documentation, reasoning)
        """
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

        # Fallback
        return content.strip(), "Generated comprehensive documentation"

    async def validate_api_key_async(self) -> bool:
        """Validate API key asynchronously.

        Returns:
            True if valid
        """
        try:
            response = await self.async_client.messages.create(
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

    def validate_api_key(self) -> bool:
        """Validate API key synchronously.

        Returns:
            True if valid
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.validate_api_key_async())


# For backward compatibility
class ClaudeClient(ClaudeClientV2):
    """Alias for ClaudeClientV2 for backward compatibility."""
    pass
