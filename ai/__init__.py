"""
===============================================================================
Falcon AI Swing Trading Platform — AI Intelligence Package Initializer
===============================================================================
Script      : __init__.py
Package     : AI Layer
===============================================================================
"""
from __future__ import annotations
from ai.synthesis_engine import AISynthesisEngine
from ai.providers import get_ai_provider

__all__ = ["AISynthesisEngine", "get_ai_provider"]