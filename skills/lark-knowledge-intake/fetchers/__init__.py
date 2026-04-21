"""Fetchers package for lark-knowledge-intake."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(module_name: str):
    module_path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = spec_from_file_location(f"lk_fetchers_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_dispatcher = _load_module("dispatcher")
_credentials = _load_module("credentials")
_types = _load_module("types")

FetchResult = _types.FetchResult
KNOWN_DOMAIN_SOURCE_TYPES = _dispatcher.KNOWN_DOMAIN_SOURCE_TYPES
PAYWALL_DOMAINS = _dispatcher.PAYWALL_DOMAINS
SUPPORTED_SOURCE_TYPES = _dispatcher.SUPPORTED_SOURCE_TYPES
detect_source_type = _dispatcher.detect_source_type
dispatch = _dispatcher.dispatch
load_local_credential = _credentials.load_local_credential

__all__ = [
    "FetchResult",
    "KNOWN_DOMAIN_SOURCE_TYPES",
    "PAYWALL_DOMAINS",
    "SUPPORTED_SOURCE_TYPES",
    "detect_source_type",
    "dispatch",
    "load_local_credential",
]
