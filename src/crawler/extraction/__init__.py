from .css_fallback import DOMAIN_FALLBACK_RULES, SelectorRule, apply_css_fallback
from .structured_data import StructuredDataResult, extract_structured_data

__all__ = [
    "StructuredDataResult",
    "extract_structured_data",
    "DOMAIN_FALLBACK_RULES",
    "SelectorRule",
    "apply_css_fallback",
]
