from .advantages import extract_advantages
from .css_fallback import (
    DOMAIN_FALLBACK_RULES,
    DOMAIN_NOISE_SELECTORS,
    DOMAIN_PLACEHOLDER_PRICES,
    DOMAIN_SPEC_ROOT_SELECTORS,
    SelectorRule,
    apply_css_fallback,
    get_noise_selector,
    get_spec_root_selector,
    is_placeholder_price,
)
from .structured_data import StructuredDataResult, extract_structured_data

__all__ = [
    "extract_advantages",
    "StructuredDataResult",
    "extract_structured_data",
    "DOMAIN_FALLBACK_RULES",
    "DOMAIN_SPEC_ROOT_SELECTORS",
    "DOMAIN_PLACEHOLDER_PRICES",
    "DOMAIN_NOISE_SELECTORS",
    "SelectorRule",
    "apply_css_fallback",
    "get_spec_root_selector",
    "get_noise_selector",
    "is_placeholder_price",
]
