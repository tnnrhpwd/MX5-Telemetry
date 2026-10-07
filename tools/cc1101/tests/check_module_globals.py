#!/usr/bin/env python3
"""Static check for "module global read before assignment".

Python decides a name is LOCAL if the function assigns to it ANYWHERE in its
body. So a function that means to use shared module state, but reads that name
before its own first assignment, raises UnboundLocalError at runtime.

Nothing catches this statically by default: `py_compile`, `ast.parse` and the
editor all report the file as clean, because the code is syntactically valid.
The failure only appears on the code path that does the assigning.

That is exactly how a missing `global _ev_bursts, _ev_unit_us` in handle_line
took the CC1101 webapp's serial reader down: the exception tore down the port,
and the reconnect re-soaked for 2+5+2 = 9 seconds, which the user experienced as
the page freezing every time a capture decoded during a transmission.

Usage:
    python tests/check_module_globals.py [path ...]

Defaults to every .py under tools/cc1101. Exits 1 if anything is found.
"""
import ast
import pathlib
import sys


def module_level_names(tree):
    """Names bound at module level, not descending into function bodies."""
    out = set()

    def walk(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                out.add(node.name)
                continue                       # its locals are its own
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    _store_names(t, out)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                _store_names(node.target, out)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                _store_names(node.target, out)
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, (ast.If, ast.While)):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.Try):
                walk(node.body)
                walk(node.orelse)
                for h in node.handlers:
                    walk(h.body)
                walk(node.finalbody)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars:
                        _store_names(item.optional_vars, out)
                walk(node.body)

    walk(tree.body)
    return out


def _store_names(target, out):
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            out.add(n.id)


def scan_function(fn, module_names, problems, path, prefix=""):
    args = fn.args
    params = {a.arg for a in list(args.args) + list(args.posonlyargs)
              + list(args.kwonlyargs)}
    if args.vararg:
        params.add(args.vararg.arg)
    if args.kwarg:
        params.add(args.kwarg.arg)

    declared, reads, writes, nested = set(), {}, {}, []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nested.append(child)
                continue                       # scanned separately
            if isinstance(child, ast.Lambda):
                continue
            if isinstance(child, (ast.Global, ast.Nonlocal)):
                declared.update(child.names)
                continue
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, ast.Load):
                    reads.setdefault(child.id, child.lineno)
                else:
                    writes.setdefault(child.id, child.lineno)
            visit(child)

    visit(fn)

    for name, wline in sorted(writes.items()):
        if name in params or name in declared or name not in module_names:
            continue
        rline = reads.get(name)
        if rline is not None and rline < wline:
            problems.append((path, prefix + fn.name, name, rline, wline))

    for child in nested:
        scan_function(child, module_names, problems, path,
                      prefix + fn.name + ".")


def check(path):
    # utf-8-sig: Windows editors happily add a BOM, which ast.parse rejects.
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names = module_level_names(tree)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scan_function(node, names, problems, path)
    return problems


def main(argv):
    targets = [pathlib.Path(a) for a in argv[1:]]
    if not targets:
        targets = [pathlib.Path(__file__).resolve().parent.parent]
    files = []
    for t in targets:
        files.extend(sorted(t.rglob("*.py")) if t.is_dir() else [t])

    found = []
    for f in files:
        found.extend(check(f))

    for path, func, name, rline, wline in found:
        print("%s:%d: %s() assigns the module global `%s` at line %d but reads "
              "it at line %d first" % (path, rline, func, name, wline, rline))
        print("        -> add `global %s` to %s(), or rename the local"
              % (name, func))
    if found:
        print("\n%d problem(s) - these raise UnboundLocalError at runtime."
              % len(found))
        return 1
    print("OK: %d file(s) checked, no module global read before assignment."
          % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
