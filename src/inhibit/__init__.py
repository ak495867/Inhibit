"""Inhibit: leakage-safe adaptive factor research."""

from inhibit.config import InhibitConfig, load_config
from inhibit.research import ResearchRunner

__all__ = ["InhibitConfig", "ResearchRunner", "load_config"]
__version__ = "0.1.0"
