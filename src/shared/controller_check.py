"""Static rule check and loader for a controller file (D37; WP12 remainder).

D37: a controller is a single Python file that uses only the standard library
and nothing from this repository. It contains one class, created as
`Controller(task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s)`, whose
`step(t_s, sensor_wet)` returns (intake_on, outtake_on). It may not read the
computer's clock, pause, start threads, keep global state, or open files or
network connections. Before a run the harness checks the file for these
things (this module) and replays a run to confirm determinism (harness.py).

The check reads the source with `ast`; it never imports or executes it. It is
a guard against the listed rule breaks, not a sandbox: deliberately hidden
access (e.g. through `getattr` on a built-in object) is not detected. The
determinism replay catches hidden state that the static check misses.

Violations stop the run (architecture section 3). Warnings are recorded in
run.json only.
"""

import ast
import hashlib
import importlib.util
import itertools
import sys
from dataclasses import dataclass, field

# Modules a controller may not import, with the D37 rule each one would break.
FORBIDDEN_MODULES = {
    # reading the clock or pausing
    "time": "clock or pause", "datetime": "clock", "sched": "clock or pause",
    "signal": "clock or pause", "zoneinfo": "clock",
    # threads and processes
    "threading": "threads", "_thread": "threads", "multiprocessing": "threads",
    "concurrent": "threads", "asyncio": "threads", "subprocess": "threads",
    # files and the operating system
    "os": "files", "io": "files", "pathlib": "files", "shutil": "files",
    "tempfile": "files", "glob": "files", "fileinput": "files",
    "sqlite3": "files", "shelve": "files", "dbm": "files", "pickle": "files",
    "logging": "files", "sys": "files",
    # network
    "socket": "network", "ssl": "network", "http": "network",
    "urllib": "network", "ftplib": "network", "smtplib": "network",
    "poplib": "network", "imaplib": "network", "xmlrpc": "network",
    "socketserver": "network", "select": "network", "selectors": "network",
    "webbrowser": "network",
    # loading other code at run time (would bypass this check)
    "importlib": "dynamic import", "builtins": "dynamic import",
    "ctypes": "dynamic import", "runpy": "dynamic import",
    "pkgutil": "dynamic import", "zipimport": "dynamic import",
    "marshal": "dynamic import", "code": "dynamic import",
    "codeop": "dynamic import", "inspect": "dynamic import",
    "gc": "dynamic import",
    # sources of non-repeatable answers (WP06 K1; D37 replay)
    "random": "non-deterministic", "secrets": "non-deterministic",
    "uuid": "non-deterministic",
}

# Built-in names a controller may not use.
FORBIDDEN_NAMES = {
    "open": "files", "input": "pause", "breakpoint": "pause",
    "eval": "dynamic code", "exec": "dynamic code", "compile": "dynamic code",
    "__import__": "dynamic import", "globals": "global state",
    "exit": "process control", "quit": "process control",
}

# Values that create mutable containers; at module or class level they are
# state shared between controller instances (D36, D37 "no global state").
MUTABLE_FACTORIES = {"list", "dict", "set", "bytearray", "deque", "defaultdict",
                     "Counter", "OrderedDict", "ChainMap"}

INIT_PARAMS = ("task", "parameter", "v_sensor_ml", "q_in_ml_per_s", "t_deadline_s")
STEP_PARAMS = ("t_s", "sensor_wet")


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    detail: str

    def as_dict(self):
        return {"rule": self.rule, "line": self.line, "detail": self.detail}


@dataclass
class CheckResult:
    path: str
    sha256: str
    violations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.violations

    def as_dict(self):
        return {"ok": self.ok,
                "violations": [f.as_dict() for f in self.violations],
                "warnings": [f.as_dict() for f in self.warnings]}


def file_sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _is_mutable_value(node):
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                         ast.DictComp, ast.SetComp)):
        return True
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        return name in MUTABLE_FACTORIES
    return False


def _assigned_values(stmt):
    if isinstance(stmt, ast.Assign):
        return [stmt.value]
    if isinstance(stmt, (ast.AnnAssign, ast.AugAssign)) and stmt.value is not None:
        return [stmt.value]
    return []


def _params_after_self(fn):
    args = fn.args
    positional = [a.arg for a in args.posonlyargs + args.args]
    return positional[1:], args.vararg is not None


def check_source(source, path="<controller>"):
    """Check controller source text against D37. Returns a CheckResult."""
    result = CheckResult(path=path, sha256=hashlib.sha256(source.encode("utf-8")).hexdigest())
    bad = result.violations.append

    try:
        tree = ast.parse(source, path)
    except SyntaxError as exc:
        bad(Finding("syntax", exc.lineno or 0, str(exc.msg)))
        return result

    stdlib = set(sys.stdlib_module_names) | {"__future__"}

    def check_module(name, line):
        top = name.split(".")[0]
        if top in FORBIDDEN_MODULES:
            bad(Finding(FORBIDDEN_MODULES[top], line, f"import of {name!r}"))
        elif top not in stdlib:
            bad(Finding("not standard library", line,
                        f"import of {name!r} (repository or third-party code)"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                check_module(alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                bad(Finding("not standard library", node.lineno, "relative import"))
            else:
                check_module(node.module or "", node.lineno)
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            bad(Finding(FORBIDDEN_NAMES[node.id], node.lineno, f"use of {node.id!r}"))
        elif isinstance(node, ast.Global):
            bad(Finding("global state", node.lineno,
                        f"'global' statement for {', '.join(node.names)}"))

    # Shared mutable state at module level and class level.
    def check_level(body, where):
        for stmt in body:
            for value in _assigned_values(stmt):
                if _is_mutable_value(value):
                    bad(Finding("global state", stmt.lineno,
                                f"mutable value assigned at {where} level"))

    check_level(tree.body, "module")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    for cls in classes:
        check_level(cls.body, f"class {cls.name}")

    # Structure: one class named Controller with __init__ and step.
    controllers = [c for c in classes if c.name == "Controller"]
    if not controllers:
        bad(Finding("interface", 0, "no top-level class named 'Controller'"))
    else:
        cls = controllers[0]
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        for name, expected in (("__init__", INIT_PARAMS), ("step", STEP_PARAMS)):
            fn = methods.get(name)
            if fn is None:
                bad(Finding("interface", cls.lineno, f"Controller has no method {name!r}"))
                continue
            params, has_varargs = _params_after_self(fn)
            if len(params) != len(expected) and not has_varargs:
                bad(Finding("interface", fn.lineno,
                            f"{name} takes {len(params)} arguments after self, "
                            f"expected {len(expected)} {expected}"))
            elif params != list(expected) and not has_varargs:
                result.warnings.append(Finding(
                    "interface", fn.lineno,
                    f"{name} argument names {params} differ from D37 {list(expected)}; "
                    "the harness passes arguments by position"))
    others = [c.name for c in classes if c.name != "Controller"]
    if others:
        result.warnings.append(Finding(
            "one class", classes[0].lineno,
            f"D37 expects one class; also defines {others}"))
    for stmt in tree.body:
        if isinstance(stmt, ast.Expr) and not (
                isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)):
            result.warnings.append(Finding("code on import", stmt.lineno,
                                           "expression statement at module level"))
    return result


def check_file(path):
    """Check a controller file against D37. Never imports or runs it."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    result = check_source(source, path)
    result.sha256 = file_sha256(path)      # hash of the exact bytes on disk
    return result


_load_counter = itertools.count()


def load_controller_class(path):
    """Load the file as a new module and return its Controller class.

    Each call executes the file afresh, so no state carries over from an
    earlier run (D36). Call check_file first; this function does not check.
    """
    name = f"_controller_under_test_{next(_load_counter)}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module            # needed by e.g. dataclasses during exec
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module.Controller
