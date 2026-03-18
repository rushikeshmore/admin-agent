"""Safety tier system for AdminAgent MCP tools.

Every tool is classified by destructiveness level.
Claude reads the safety label in tool docstrings and acts accordingly.
"""

from __future__ import annotations

from enum import IntEnum


class SafetyTier(IntEnum):
    """Safety classification for Admin API tools."""

    EXCLUDED = -2  # Never built (payments, domains, checkout, tax)
    READ_ONLY = -1  # View-only resources, no mutations
    READ = 0  # Read operations, no confirmation needed
    WRITE = 1  # Create/update, show preview before executing
    DESTRUCTIVE = 2  # Delete operations, require explicit confirmation
    BULK = 3  # Affect many resources, require count + preview + confirm


_LABELS = {
    SafetyTier.EXCLUDED: "[EXCLUDED — This operation is not available]",
    SafetyTier.READ_ONLY: "[SAFETY: Read-Only — No modifications possible]",
    SafetyTier.READ: "[SAFETY: Tier 0 — Read]",
    SafetyTier.WRITE: "[SAFETY: Tier 1 — Write] Show what will change before executing.",
    SafetyTier.DESTRUCTIVE: "[SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.",
    SafetyTier.BULK: "[SAFETY: Tier 3 — Bulk] Show count and preview, then confirm before executing.",
}

# Registry: tool_name -> SafetyTier
TOOL_SAFETY: dict[str, SafetyTier] = {}


def register_safety(tool_name: str, tier: SafetyTier) -> None:
    """Register a tool's safety tier."""
    TOOL_SAFETY[tool_name] = tier


def get_safety_tier(tool_name: str) -> SafetyTier:
    """Get a tool's safety tier. Defaults to READ if not registered."""
    return TOOL_SAFETY.get(tool_name, SafetyTier.READ)


def safety_label(tier: SafetyTier) -> str:
    """Human-readable label for tool docstrings."""
    return _LABELS.get(tier, "[SAFETY: Unknown]")
