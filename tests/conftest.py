from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


class MacroReturn(Exception):
    def __init__(self, value):
        self.value = value


def macro_return(value):
    raise MacroReturn(value)


def compiler_error(message):
    raise ValueError(message)


class MacroHarness:
    def __init__(self):
        self.environment = Environment(extensions=["jinja2.ext.do"], undefined=StrictUndefined)
        self.package = SimpleNamespace()
        self.context = {
            "dbt_cortex_agent": self.package,
            "return": macro_return,
            "exceptions": SimpleNamespace(raise_compiler_error=compiler_error),
            "modules": SimpleNamespace(re=re),
            "tojson": json.dumps,
            "fromjson": json.loads,
            "fromyaml": yaml.safe_load,
            "execute": True,
            "log": lambda *args, **kwargs: "",
        }
        self.sources = {}
        for path in (ROOT / "macros").rglob("*.sql"):
            source = path.read_text(encoding="utf-8")
            source = re.sub(
                r"{% materialization (\w+), adapter='snowflake' %}",
                r"{% macro materialization_\1() %}",
                source,
            ).replace("{% endmaterialization %}", "{% endmacro %}")
            for match in re.finditer(r"{% macro (\w+)\(.*?{% endmacro %}", source, re.DOTALL):
                name = match.group(1)
                self.sources[name] = match.group(0)
                self.override(name, self._callable(name))

    def _callable(self, name):
        def invoke(*args, **kwargs):
            module = self.environment.from_string(self.sources[name]).make_module(self.context)
            try:
                return getattr(module, name)(*args, **kwargs)
            except MacroReturn as result:
                return result.value

        return invoke

    def override(self, name, implementation):
        setattr(self.package, name, implementation)
        self.context[name] = implementation

    def call(self, name, *args, **kwargs):
        return getattr(self.package, name)(*args, **kwargs)


@pytest.fixture
def macro_harness():
    return MacroHarness()


@pytest.fixture
def collected_test_nodes(request):
    cache = {}

    def collect(path):
        path = Path(path).resolve()
        if path not in cache:
            module = pytest.Module.from_parent(request.session, path=path)
            items = list(request.session.genitems(module))
            selectors = {}
            for item in items:
                selectors.setdefault(item.nodeid, set()).add(item.nodeid)
                if isinstance(item, pytest.Function):
                    function = f"{item.parent.nodeid}::{item.originalname or item.name}"
                    selectors.setdefault(function, set()).add(item.nodeid)
            cache[path] = selectors
        return cache[path]

    return collect
