"""Shared pytest fixtures for HELIOS test suite."""
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
