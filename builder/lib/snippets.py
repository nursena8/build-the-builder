"""Build the Python text of a Freya code node: spec constants + the tested helpers in cal.py + the node's own body.

    import sys; sys.path.insert(0, "lib")
    from snippets import code
    node_code = code(BODY, spec_subset)      # BODY may use SPEC[...] and every function of cal.py

The result is a string for the `code` default of a code_exec action. SPEC is the dict you pass (JSON-safe).
"""
import json, pathlib

_HERE = pathlib.Path(__file__).resolve().parent
LIB = (_HERE / "cal.py").read_text()


def code(body, spec=None):
    return "import json\nSPEC = json.loads(" + repr(json.dumps(spec or {})) + ")\n" + LIB + "\n" + body
