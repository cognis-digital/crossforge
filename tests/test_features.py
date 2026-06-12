"""Feature tests for crossforge — new transforms, render_all, explain, CLI."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crossforge import explain, load, render, render_all
from crossforge.core import _apply_transform, _substitute
from crossforge.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(REPO_ROOT, "demos", "01-basic")
DEF, COMP, CLAIM = (os.path.join(D, f) for f in
                    ("definition.yaml", "composition.yaml", "claim.yaml"))


class TestNewTransforms(unittest.TestCase):
    def test_prefix(self):
        self.assertEqual(_apply_transform("svc", {"type": "prefix", "value": "prod-"}),
                         "prod-svc")

    def test_suffix(self):
        self.assertEqual(_apply_transform("app", {"type": "suffix", "value": ".local"}),
                         "app.local")

    def test_int(self):
        self.assertEqual(_apply_transform("42", {"type": "int"}), 42)
        self.assertEqual(_apply_transform("x", {"type": "int", "default": 7}), 7)

    def test_upper_lower(self):
        self.assertEqual(_apply_transform("aB", {"type": "upper"}), "AB")
        self.assertEqual(_apply_transform("aB", {"type": "lower"}), "ab")

    def test_chained_transforms_in_substitute(self):
        out = _substitute("${name | prefix | upper}", {"name": "svc"},
                          {"prefix": {"type": "prefix", "value": "x-"},
                           "upper": {"type": "upper"}})
        self.assertEqual(out, "X-SVC")


class TestRenderAll(unittest.TestCase):
    def test_batch_two_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1 = os.path.join(tmp, "c1.yaml")
            c2 = os.path.join(tmp, "c2.yaml")
            with open(c1, "w") as fh:
                fh.write("kind: Database\nmetadata:\n  name: orders\n"
                         "spec:\n  parameters:\n    engine: postgres\n    size: small\n")
            with open(c2, "w") as fh:
                fh.write("kind: Database\nmetadata:\n  name: billing\n"
                         "spec:\n  parameters:\n    engine: mysql\n    size: large\n")
            out = render_all(load(DEF), load(COMP), [load(c1), load(c2)])
            self.assertEqual(set(out), {"orders", "billing"})
            self.assertEqual(len(out["orders"]), 2)
            # each claim rendered independently
            img = out["billing"][0]["spec"]["template"]["spec"]["containers"][0]["image"]
            self.assertIn("mysql", img)


class TestExplain(unittest.TestCase):
    def test_explain_lists_placeholders(self):
        res = explain(load(DEF), load(COMP), load(CLAIM))
        self.assertEqual(res["claim_name"], "orders")
        self.assertIn("engine", res["params"])
        kinds = {r["kind"] for r in res["resources"]}
        self.assertIn("StatefulSet", kinds)
        ss = next(r for r in res["resources"] if r["kind"] == "StatefulSet")
        self.assertTrue(any("engine" in ph for ph in ss["placeholders"]))


class TestCliFeatures(unittest.TestCase):
    def test_explain_cli(self):
        self.assertEqual(main(["explain", "--definition", DEF,
                               "--composition", COMP, "--claim", CLAIM]), 0)

    def test_render_all_cli(self):
        self.assertEqual(main(["render-all", "--definition", DEF,
                               "--composition", COMP, "--claim", CLAIM]), 0)

    def test_render_all_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "all.json")
            self.assertEqual(main(["render-all", "--definition", DEF,
                                   "--composition", COMP, "--claim", CLAIM,
                                   "--out", out]), 0)
            with open(out) as fh:
                data = json.load(fh)
            self.assertIn("orders", data)


if __name__ == "__main__":
    unittest.main()
