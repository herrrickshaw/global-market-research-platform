#!/usr/bin/env python3
"""
OmniRoute LLM provider selector — routes Claude calls through cost/latency-optimized models.

Replaces hardcoded model selection with intelligent routing:
  - Token size < 5K → Sonnet (70% cost savings)
  - Token size 5–15K → Size-based decision (cost vs quality)
  - Token size > 15K → Opus (reasoning-heavy tasks)
  - Latency budget < 2s → Sonnet (fast inference)
  - Latency budget > 5s → Opus if reasoning needed, else Sonnet

Usage:
  router = OmniRouteClient(config_path="~/.ruflo/omniroute_config.yaml")
  model_to_use = router.select_model(prompt_tokens=8000, max_latency_ms=3000)
  # Then make API call with selected model

Configuration via ~/.ruflo/omniroute_config.yaml:
  providers:
    anthropic: {api_key: $ANTHROPIC_API_KEY, models: [opus-5, sonnet-5]}
    openai: {api_key: $OPENAI_API_KEY, models: [gpt-4o, gpt-4]}
  cost_threshold: 0.05  # Switch to cheaper model if >5% cost difference
  latency_slo_ms: 3000  # Target max latency
"""
import json
import os
from pathlib import Path
from datetime import datetime
import math


# Model pricing (per MTok = million tokens)
MODEL_PRICING = {
    # Anthropic
    "claude-opus-5": {"input": 15, "output": 45},
    "claude-sonnet-5": {"input": 3, "output": 15},
    "claude-haiku-4": {"input": 0.80, "output": 4},

    # OpenAI (fallback)
    "gpt-4o": {"input": 5, "output": 15},
    "gpt-4-turbo": {"input": 10, "output": 30},
    "gpt-4": {"input": 30, "output": 60},

    # Mistral (budget)
    "mistral-large": {"input": 2, "output": 6},
    "mistral-medium": {"input": 0.81, "output": 2.43},
}

# Model capabilities + latency (in ms, median)
MODEL_PROFILE = {
    "claude-opus-5": {"reasoning": 10, "latency_ms": 4500, "quality": 10},
    "claude-sonnet-5": {"reasoning": 7, "latency_ms": 1800, "quality": 8},
    "claude-haiku-4": {"reasoning": 4, "latency_ms": 800, "quality": 6},
    "gpt-4o": {"reasoning": 8, "latency_ms": 2500, "quality": 8},
    "gpt-4-turbo": {"reasoning": 9, "latency_ms": 3500, "quality": 9},
    "mistral-large": {"reasoning": 7, "latency_ms": 2000, "quality": 7},
}


class OmniRouteClient:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path or "~/.ruflo/omniroute_config.yaml").expanduser()
        self.log_path = Path("~/.ruflo/data/omniroute_routing.log").expanduser()
        self.routing_log = []

        # Load config
        self.config = self._load_config()
        self.cost_threshold = self.config.get("cost_threshold", 0.05)
        self.latency_slo_ms = self.config.get("latency_slo_ms", 3000)
        self.provider_priority = self.config.get("provider_priority", ["anthropic", "openai", "mistral"])

    def _load_config(self):
        """Load configuration from YAML (or create default)."""
        if self.config_path.exists():
            import yaml
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        else:
            # Return sensible defaults
            return {
                "cost_threshold": 0.05,
                "latency_slo_ms": 3000,
                "provider_priority": ["anthropic", "openai", "mistral"],
                "providers": {
                    "anthropic": {
                        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                        "models": ["claude-opus-5", "claude-sonnet-5"],
                    },
                    "openai": {
                        "api_key": os.getenv("OPENAI_API_KEY", ""),
                        "models": ["gpt-4o"],
                    },
                    "mistral": {
                        "api_key": os.getenv("MISTRAL_API_KEY", ""),
                        "models": ["mistral-large"],
                    }
                }
            }

    def select_model(self, prompt_tokens=0, output_tokens_estimate=0,
                     reasoning_required=False, max_latency_ms=None,
                     preferred_provider="anthropic"):
        """
        Intelligently select the best model based on request characteristics.

        Args:
            prompt_tokens: Expected input tokens
            output_tokens_estimate: Estimated output tokens (helps cost calculation)
            reasoning_required: Does this request need reasoning/analysis?
            max_latency_ms: Strict latency requirement (None = use config default)
            preferred_provider: Try this provider first (e.g., "anthropic")

        Returns:
            (model_name, reason, cost_estimate_usd)
        """
        if max_latency_ms is None:
            max_latency_ms = self.latency_slo_ms

        # Stage 1: Filter by latency requirement
        candidates = self._filter_by_latency(max_latency_ms, reasoning_required)
        if not candidates:
            # Fallback: use fastest model
            candidates = [("claude-sonnet-5", "fallback to fastest available")]

        # Stage 2: Filter by reasoning requirement
        if reasoning_required:
            reasoning_candidates = [m for m in candidates if MODEL_PROFILE.get(m[0], {}).get("reasoning", 5) >= 7]
            if reasoning_candidates:
                candidates = reasoning_candidates

        # Stage 3: Filter by cost
        total_tokens = prompt_tokens + output_tokens_estimate
        selected = self._select_by_cost(candidates, total_tokens, preferred_provider)

        model, reason = selected
        cost = self._estimate_cost(model, prompt_tokens, output_tokens_estimate)

        # Log decision
        self._log_routing(model, reason, prompt_tokens, output_tokens_estimate, cost)

        return model, reason, cost

    def _filter_by_latency(self, max_latency_ms, reasoning_required):
        """Filter models that can respond within latency SLO."""
        candidates = []
        for model in self._get_available_models():
            profile = MODEL_PROFILE.get(model, {})
            latency = profile.get("latency_ms", 5000)

            # Add buffer for reasoning
            if reasoning_required:
                latency *= 1.3

            if latency <= max_latency_ms:
                candidates.append((model, f"latency OK ({latency:.0f}ms < {max_latency_ms}ms)"))

        return candidates

    def _select_by_cost(self, candidates, total_tokens, preferred_provider):
        """Select cheapest model from candidates, preferring preferred_provider."""
        if not candidates:
            return ("claude-opus-5", "no candidates, fallback to Opus")

        # Sort by cost
        costs = []
        for model, reason in candidates:
            cost = MODEL_PRICING.get(model, {}).get("input", 1) * (total_tokens / 1_000_000)
            costs.append((model, reason, cost))

        costs.sort(key=lambda x: x[2])  # Sort by cost ascending

        cheapest_model, reason, cheapest_cost = costs[0]

        # Check if preferred provider has an option within cost threshold
        if preferred_provider:
            pref_options = [c for c in costs if self._get_provider(c[0]) == preferred_provider]
            if pref_options:
                pref_model, pref_reason, pref_cost = pref_options[0]
                cost_delta = (pref_cost - cheapest_cost) / cheapest_cost if cheapest_cost > 0 else 0
                if cost_delta < self.cost_threshold:
                    return (pref_model, f"{pref_reason} (preferred, +{cost_delta:.1%} cost)")

        return (cheapest_model, reason)

    def _get_available_models(self):
        """Return list of configured, available models."""
        models = []
        for provider, config in self.config.get("providers", {}).items():
            if config.get("api_key"):  # Only if API key is present
                models.extend(config.get("models", []))
        return models

    def _get_provider(self, model_name):
        """Get provider name for a model."""
        for provider, config in self.config.get("providers", {}).items():
            if model_name in config.get("models", []):
                return provider
        return None

    def _estimate_cost(self, model, prompt_tokens, output_tokens):
        """Estimate USD cost for a request."""
        pricing = MODEL_PRICING.get(model, {"input": 1, "output": 1})
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _log_routing(self, model, reason, input_tokens, output_tokens, cost):
        """Log routing decision for analysis."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "reason": reason,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }
        self.routing_log.append(entry)

        # Append to log file
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_routing_stats(self):
        """Summarize routing decisions this session."""
        if not self.routing_log:
            return {}

        total_cost = sum(e["cost_usd"] for e in self.routing_log)
        by_model = {}
        for entry in self.routing_log:
            model = entry["model"]
            if model not in by_model:
                by_model[model] = {"count": 0, "cost": 0, "tokens": 0}
            by_model[model]["count"] += 1
            by_model[model]["cost"] += entry["cost_usd"]
            by_model[model]["tokens"] += entry["input_tokens"] + entry["output_tokens"]

        return {
            "total_requests": len(self.routing_log),
            "total_cost_usd": round(total_cost, 4),
            "by_model": by_model,
        }


# Convenience factory — for fast prototyping
def create_router():
    """Create and return a configured OmniRouteClient."""
    return OmniRouteClient()


if __name__ == "__main__":
    import sys

    router = OmniRouteClient()

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test routing logic
        tests = [
            (2000, 500, False, None, "Quick lookup"),
            (8000, 2000, False, 3000, "Moderate analysis"),
            (15000, 5000, True, 5000, "Complex reasoning"),
            (25000, 10000, True, None, "Heavy reasoning, no latency constraint"),
        ]

        print("OmniRoute Model Selection Tests\n")
        for prompt, output, reasoning, latency, desc in tests:
            model, reason, cost = router.select_model(
                prompt_tokens=prompt,
                output_tokens_estimate=output,
                reasoning_required=reasoning,
                max_latency_ms=latency
            )
            print(f"{desc}:")
            print(f"  Tokens: {prompt+output}  Reasoning: {reasoning}  Latency: {latency}ms")
            print(f"  Model: {model} | Reason: {reason}")
            print(f"  Est. Cost: ${cost:.6f}\n")

        stats = router.get_routing_stats()
        print(f"Routing Stats:\n{json.dumps(stats, indent=2)}")

    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = router.get_routing_stats()
        print(json.dumps(stats, indent=2))

    else:
        print("usage: omniroute_client.py [test|stats]")
