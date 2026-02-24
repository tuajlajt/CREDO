"""
Configuration loader.

Loads YAML config files into Python dicts (and optionally dataclasses).
All model IDs, paths, and thresholds must come from configs/ — never hardcoded in src/.

Usage:
    from src.config.loader import load_config
    config = load_config()
    model_id = config["models"]["medgemma"]

Owner agent: code-architect
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path("configs/default.yaml")


def load_config(path: Optional[Path] = None) -> dict:
    """
    Load the default config (or a specified config file).
    Returns a nested dict with all config values.

    Args:
        path: Path to YAML config file. Defaults to configs/default.yaml.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model_config(model_name: str) -> dict:
    """
    Load a model-specific config from configs/models/{model_name}.yaml.
    Merges with default config.
    """
    model_config_path = Path(f"configs/models/{model_name}.yaml")
    if not model_config_path.exists():
        raise FileNotFoundError(f"Model config not found: {model_config_path}")
    base = load_config()
    with open(model_config_path, encoding="utf-8") as f:
        model_cfg = yaml.safe_load(f)
    base.update(model_cfg)
    return base


def load_agent_config(agent_name: str) -> dict:
    """
    Load an agent-specific config from configs/agents/{agent_name}.yaml.
    """
    agent_config_path = Path(f"configs/agents/{agent_name}.yaml")
    if not agent_config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {agent_config_path}")
    with open(agent_config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
