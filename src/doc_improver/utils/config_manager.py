"""Configuration management for the documentation improver."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from pydantic import ValidationError

from doc_improver.models import ExplorationConfig, GenerationConfig


class ConfigManager:
    """Manages configuration loading and validation."""

    DEFAULT_CONFIG_PATHS = [
        Path.cwd() / ".doc-improver.yaml",
        Path.cwd() / ".doc-improver.yml",
        Path.home() / ".config" / "doc-improver" / "config.yaml",
    ]

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file or defaults."""
        if self.config_path and self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            return

        # Try default locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                with open(path, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
                self.config_path = path
                return

        # Use empty config if no file found
        self.config = {}

    def get_exploration_config(
        self,
        target_type: str,
        target: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> ExplorationConfig:
        """Get exploration configuration with overrides.

        Args:
            target_type: Type of target (code, website, etc.)
            target: Path or URL to explore
            overrides: Optional configuration overrides

        Returns:
            ExplorationConfig instance
        """
        config_dict = {
            "target_type": target_type,
            "target_path_or_url": target,
        }

        # Merge from config file
        if "exploration" in self.config:
            config_dict.update(self.config["exploration"])

        # Apply overrides
        if overrides:
            config_dict.update(overrides)

        try:
            return ExplorationConfig(**config_dict)
        except ValidationError as e:
            raise ValueError(f"Invalid exploration configuration: {e}")

    def get_generation_config(
        self,
        overrides: Optional[Dict[str, Any]] = None
    ) -> GenerationConfig:
        """Get generation configuration with overrides.

        Args:
            overrides: Optional configuration overrides

        Returns:
            GenerationConfig instance
        """
        config_dict = {}

        # Get API key from environment
        config_dict["api_key"] = os.getenv("ANTHROPIC_API_KEY")

        # Merge from config file
        if "generation" in self.config:
            config_dict.update(self.config["generation"])

        # Apply overrides
        if overrides:
            config_dict.update(overrides)

        try:
            return GenerationConfig(**config_dict)
        except ValidationError as e:
            raise ValueError(f"Invalid generation configuration: {e}")

    def save_config(self, path: Optional[Path] = None) -> None:
        """Save current configuration to file.

        Args:
            path: Optional path to save to (uses current config_path if not provided)
        """
        save_path = path or self.config_path or self.DEFAULT_CONFIG_PATHS[0]
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False, indent=2)

    @staticmethod
    def create_default_config(path: Path) -> None:
        """Create a default configuration file.

        Args:
            path: Path where to create the config file
        """
        default_config = {
            "exploration": {
                "mode": "standard",
                "max_depth": 10,
                "follow_links": True,
                "analyze_comments": True,
                "exclude_patterns": [
                    "**/__pycache__/**",
                    "**/node_modules/**",
                    "**/.git/**",
                    "**/venv/**",
                ]
            },
            "generation": {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.3,
                "max_tokens": 4000,
                "style": "google",
                "include_examples": True,
                "include_type_hints": True,
                "auto_apply": False,
            }
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.safe_dump(default_config, f, default_flow_style=False, indent=2)
