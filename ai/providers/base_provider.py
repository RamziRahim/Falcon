# ai/providers/base_provider.py
from __future__ import annotations
from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    @abstractmethod
    def generate_structured_synthesis(self, formatted_prompt: str) -> dict:
        """Must accept a prompt payload string and return a valid Python dictionary."""
        pass

    def _get_fallback_packet(self, error_message: str) -> dict:
        """Universal fail-safe configuration to prevent execution crashes."""
        return {
            "velocity_score": 0,
            "growth_divergence_flag": False,
            "fundamental_growth_synthesis": f"PROVIDER RECOVERY ACTIVE: {error_message}",
            "supply_and_float_verdict": "UNKNOWN DUE TO SYSTEM DECOUPLING",
            "executive_action": "ALERT_WATCHLIST"
        }