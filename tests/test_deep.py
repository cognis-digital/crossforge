"""Deep tests for crossforge — params, transforms, validation, errors, MCP."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crossforge import (
    draft_composition, load, render, resolve_params, validate_composition,
)
from crossforge.core import CrossforgeError, _apply_transform, _substitute
from crossforge import mcp_server

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(REPO_ROOT, "demos", "01-basic")
DEF, COMP, CLAIM = (os.path.join(D, f) for f in
                    ("definition.yaml", "composition.yaml", "claim.yaml"))


class TestParams(unittest.TestCase):
    def test_defaults_applied(self):
        definition = {"spec": {"parameters": {"a": {"default": 5}, "b": {}}}}
        p = resolve_params(definition, {"metadata": {"name": "c"}, "spec": {"parameters": {}}})
        self.assertEqual(p["a"], 5)
        self.assertIsNone(p["b"])

    def test_required_missing(self):
        definition = {"spec": {"parameters": {"a": {"required": True}}}}
        with self.assertRaises(CrossforgeError):
            resolve_params(definition, {"spec": {"parameters": {}}})

    def test_enum_violation(self):
        definition = {"spec": {"parameters": {"a": {"enum": ["x", "y"]}}}}
        with self.assertRaises(CrossforgeError):
            resolve_params(definition, {"spec": {"parameters": {"a": "z"}}})

    def test_unknown_param(self):
        definition = {"spec": {"parameters": {"a": {}}}}
        with self.assertRaises(CrossforgeError):
            resolve_params(definition, {"spec": {"parameters": {"typo": 1}}})


class TestTransforms(unittest.TestCase):
    def test_map(self):
        self.assertEqual(_apply_transform("small", {"type": "map",
                         "map": {"small": "250m"}}), "250m")

    def test_map_default(self):
        self.assertEqual(_apply_transform("xl", {"type": "map", "map": {},
                         "default": "250m"}), "250m")

    def test_format(self):
        self.assertEqual(_apply_transform(10, {"type": "format", "fmt": "{}Gi"}), "10Gi")

    def test_substitute_preserves_type(self):
        out = _substitute({"n": "${x}"}, {"x": 50}, {})
        self.assertEqual(out["n"], 50)  # int preserved, not "50"

    def test_substitute_inline_string(self):
        out = _substitute("name-${x}", {"x": "abc"}, {})
        self.assertEqual(out, "name-abc")


class TestValidate(unittest.TestCase):
    def test_demo_valid(self):
        self.assertTrue(validate_composition(load(DEF), load(COMP))["ok"])

    def test_undeclared_param(self):
        definition = {"spec": {"parameters": {"a": {}}}}
        composition = {"spec": {"resources": [{"base": {"x": "${ghost}"}}]}}
        res = validate_composition(definition, composition)
        self.assertFalse(res["ok"])
        self.assertTrue(any("ghost" in p for p in res["problems"]))

    def test_unknown_transform(self):
        definition = {"spec": {"parameters": {"a": {}}}}
        composition = {"spec": {"resources": [{"base": {"x": "${a | nope}"}}]}}
        res = validate_composition(definition, composition)
        self.assertFalse(res["ok"])


class TestMcp(unittest.TestCase):
    def test_render_and_validate(self):
        tl = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual({t["name"] for t in tl["result"]["tools"]}, {"render", "validate"})
        r = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "render",
                       "arguments": {"definition": DEF, "composition": COMP,
                                     "claim": CLAIM}}})
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertEqual(len(payload["resources"]), 2)

    def test_validate_error_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "d.json")
            c = os.path.join(tmp, "c.json")
            with open(d, "w") as fh:
                json.dump({"spec": {"parameters": {"a": {}}}}, fh)
            with open(c, "w") as fh:
                json.dump({"spec": {"resources": [{"base": {"x": "${ghost}"}}]}}, fh)
            r = mcp_server.handle_request({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "validate",
                           "arguments": {"definition": d, "composition": c}}})
            self.assertTrue(r["result"]["isError"])


class TestAiHook(unittest.TestCase):
    def test_off_by_default(self):
        for v in ("COGNIS_AI_BACKEND", "COGNIS_AI_ENDPOINT"):
            os.environ.pop(v, None)
        out = draft_composition("a managed redis cache abstraction")
        self.assertTrue(out["_ai"].startswith("disabled"))


if __name__ == "__main__":
    unittest.main()
