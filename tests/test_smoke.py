"""Smoke tests for crossforge. Standard library only."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crossforge import TOOL_NAME, TOOL_VERSION, load, render
from crossforge.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(REPO_ROOT, "demos", "01-basic")
DEF, COMP, CLAIM = (os.path.join(D, f) for f in
                    ("definition.yaml", "composition.yaml", "claim.yaml"))


class TestMetadata(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "crossforge")
        self.assertTrue(TOOL_VERSION)


class TestRender(unittest.TestCase):
    def test_render_demo(self):
        out = render(load(DEF), load(COMP), load(CLAIM))
        self.assertEqual(len(out), 2)
        ss = out[0]
        self.assertEqual(ss["kind"], "StatefulSet")
        self.assertEqual(ss["metadata"]["name"], "orders-db")
        c = ss["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(c["image"], "localhost:5000/postgres:16")
        self.assertEqual(c["resources"]["requests"]["cpu"], "500m")  # medium
        pvc = out[1]
        self.assertEqual(pvc["spec"]["resources"]["requests"]["storage"], 50)


class TestCli(unittest.TestCase):
    def test_render(self):
        self.assertEqual(main(["render", "--definition", DEF,
                               "--composition", COMP, "--claim", CLAIM]), 0)

    def test_validate(self):
        self.assertEqual(main(["validate", "--definition", DEF,
                               "--composition", COMP]), 0)

    def test_params(self):
        self.assertEqual(main(["params", "--definition", DEF, "--claim", CLAIM]), 0)

    def test_no_command_exits_2(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
