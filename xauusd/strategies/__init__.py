from .base import Strategy
from .breakout import Breakout
from .smc import SmartMoney
from .trend import TrendPullback

REGISTRY = {
    "breakout": Breakout,
    "trend": TrendPullback,
    "smc": SmartMoney,
}

__all__ = ["Strategy", "Breakout", "TrendPullback", "SmartMoney", "REGISTRY"]
