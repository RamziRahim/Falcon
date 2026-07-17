"""
===============================================================================
Falcon AI Swing Trading Platform — Decoupled Gemini Provider with Auto-Failover
===============================================================================
Script      : gemini_provider.py
Package     : AI Layer / Providers
===============================================================================
"""
from __future__ import annotations
import os
import json
import time
import google.generativeai as genai
from ai.providers.base_provider import BaseAIProvider

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        # Loaded from a local .env file (see .env.example) — never hardcoded here.
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "[API ERROR] GEMINI_API_KEY not found. Create a .env file in the "
                "project root (copy .env.example) and add your real Gemini API key."
            )

        genai.configure(api_key=api_key)
        
        # Internal engine states
        self.model_name = "gemini-2.5-flash"
        self.model = genai.GenerativeModel(self.model_name)
        self.consecutive_failures = 0
        self.is_fallback_active = False

    def generate_structured_synthesis(self, formatted_prompt: str) -> dict:
        """Sends data payload to Google API with encapsulated failover resilience."""
        try:
            return self._execute_inference(formatted_prompt)
        except Exception as e:
            err_msg = str(e)
            # Check for Rate Limit / Quota Exceeded (HTTP 429)
            if "429" in err_msg or "Quota exceeded" in err_msg:
                self.consecutive_failures += 1
                print(f"  ⚠️  [PROVIDER WARNING] Gemini Rate Limit hit. Active Cooldown initiated...")
                
                # If we strike out repeatedly, dynamically downgrade internal engine target
                if self.consecutive_failures >= 2 and not self.is_fallback_active:
                    print("  🔥 [PROVIDER INTERNAL HOT-SWAP] Toggling target architecture to gemini-2.5-flash...")
                    self.model_name = "gemini-2.5-flash"
                    self.model = genai.GenerativeModel(self.model_name)
                    self.is_fallback_active = True
                
                # Wait out the quota window burst burst limit
                time.sleep(15)
                
                # Recursive retry immediately utilizing updated provider settings
                try:
                    return self._execute_inference(formatted_prompt)
                except Exception as retry_err:
                    return self._get_fallback_packet(f"Retry attempt failed: {retry_err}")
            else:
                # Reset failure counter on non-rate-limit unexpected breaks
                self.consecutive_failures = 0
                return self._get_fallback_packet(err_msg)

    def _execute_inference(self, prompt: str) -> dict:
        """Executes raw transaction channel with Gemini endpoint."""
        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        if not response.text:
            raise ValueError("Zero length character stream returned by LLM engine.")
            
        # Decoupled success loop: tracking healthy connections
        self.consecutive_failures = max(0, self.consecutive_failures - 1)
        return json.loads(response.text.strip())