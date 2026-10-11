"""python3 dev/test_rulecheck.py"""
import json, pathlib, subprocess, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "builder"))
import rulecheck


def folder(brief, coverage, scenarios):
    d = pathlib.Path(tempfile.mkdtemp()); (d / "inputs").mkdir(); (d / "out").mkdir()
    (d / "inputs" / "b.md").write_text(brief); (d / "out" / "coverage.json").write_text(json.dumps(coverage)); (d / "out" / "scenarios.json").write_text(json.dumps(scenarios))
    return d


BRIEF = "# T\n1. First.\n2. Second.\n3. Third.\n4. Fourth.\n5. Fifth.\n"


class Rules(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(rulecheck.rule_ids(folder(BRIEF, {}, [])), {1, 2, 3, 4, 5})
    def test_expand(self):
        self.assertEqual(rulecheck.expand("A5-A7"), {5, 6, 7}); self.assertEqual(rulecheck.expand("B1, B2"), {1, 2}); self.assertEqual(rulecheck.expand(9), {9})
    def test_pass(self):
        d = folder(BRIEF, {"1-5": "step code"}, [{"name": "a", "rules": [1, 2, 3, 4]}])
        self.assertEqual(rulecheck.main(["x", str(d)]), 0)
    def test_missing_coverage_fails(self):
        d = folder(BRIEF, {"1-4": "step code", "5": ""}, [{"rules": [1, 2, 3, 4, 5]}])
        self.assertEqual(rulecheck.main(["x", str(d)]), 1)
    def test_untested_fails_and_wording_is_exempt(self):
        d = folder(BRIEF, {"1-3": "step", "4": "wording: tone", "5": "wording: tone"}, [{"rules": [1]}])
        self.assertEqual(rulecheck.main(["x", str(d)]), 0)        # 1 tested + 2 wording... 3 rules untested of 5? 2,3 untested -> 60% tested
        d = folder(BRIEF, {"1-5": "step"}, [{"rules": [1]}])
        self.assertEqual(rulecheck.main(["x", str(d)]), 1)
    def test_no_numbered_rules(self):
        d = folder("just prose", {}, [])
        self.assertEqual(rulecheck.main(["x", str(d)]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
