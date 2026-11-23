"""Shared loader for the gmrp offline tests (not collected: no ``test_`` prefix).

Modules are loaded by file path under a private name so nothing here depends
on, or pollutes, the repo's import layout; ``sys.modules`` entries added during
a load are restored by the callers' fixtures.
"""
import importlib.util
import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def path(*parts):
    return os.path.join(ROOT, *parts)


def load(name, *parts):
    spec = importlib.util.spec_from_file_location(name, path(*parts))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fake_module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m
