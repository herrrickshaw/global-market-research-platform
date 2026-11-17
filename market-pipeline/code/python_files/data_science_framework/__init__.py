"""
Data Science Framework v1.0
Unified pipeline for market analysis across all 40+ repos.

Synthesizes:
- Data Analysis Using SQL and Excel (Linoff)
- Python for Data Analysis (McKinney)
- Data Mining: Concepts and Techniques (Han/Kamber/Pei)
- Storytelling with Data (Knaflic)

Usage:
    from data_science_framework import (
        DataPipeline, FeatureEngineering, TrendSignals,
        RegimeDetection, ModelEvaluation, Storytelling
    )
"""

from .core import (
    DataQualityReport,
    DataPipeline,
    FeatureEngineering,
    StatisticalTesting,
    PatternDiscovery,
    ModelEvaluation,
    Storytelling,
)

from .market_signals import (
    Signal,
    TrendSignals,
    MeanReversionSignals,
    RegimeDetection,
    SignalComposition,
    SignalBacktest,
)

__version__ = "1.0.0"
__author__ = "Data Science Team"

__all__ = [
    # Core
    "DataQualityReport",
    "DataPipeline",
    "FeatureEngineering",
    "StatisticalTesting",
    "PatternDiscovery",
    "ModelEvaluation",
    "Storytelling",
    # Signals
    "Signal",
    "TrendSignals",
    "MeanReversionSignals",
    "RegimeDetection",
    "SignalComposition",
    "SignalBacktest",
]
