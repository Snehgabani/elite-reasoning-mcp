"""
AST Symbol Outliner & Call Graph Explorer (LSP-over-MCP / Serena Style).
Extracts typed interface outlines and directional call-hierarchy graphs without function bodies,
cutting LLM context token consumption by ~90-97% and providing deterministic blast-radius analysis.
"""

from __future__ import annotations

import ast
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field


class FunctionSymbol(BaseModel):
    name: str
    line_number: int
    is_async: bool = False
    args: List[str] = Field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)


class ClassSymbol(BaseModel):
    name: str
    line_number: int
    bases: List[str] = Field(default_factory=list)
    docstring: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)
    methods: List[FunctionSymbol] = Field(default_factory=list)


class OutlineResult(BaseModel):
    filename: str = "snippet.py"
    total_raw_lines: int = 0
    total_outline_lines: int = 0
    token_reduction_pct: float = 0.0
    classes: List[ClassSymbol] = Field(default_factory=list)
    functions: List[FunctionSymbol] = Field(default_factory=list)
    skeleton_code: str = ""
    schema_version: str = "1.0.0"


class CallGraphNode(BaseModel):
    symbol_name: str
    defined_at_line: int
    callees: List[str] = Field(default_factory=list)
    callers: List[str] = Field(default_factory=list)


class CallGraphResult(BaseModel):
    filename: str = "snippet.py"
    total_symbols: int = 0
    nodes: Dict[str, CallGraphNode] = Field(default_factory=dict)
    schema_version: str = "1.0.0"

    def get_blast_radius(self, modified_symbol: str) -> List[str]:
        """Returns all upstream functions/methods directly or indirectly calling modified_symbol."""
        visited: Set[str] = set()
        queue = [modified_symbol]
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                node = self.nodes.get(curr)
                if node:
                    for caller in node.callers:
                        if caller not in visited:
                            queue.append(caller)
        visited.discard(modified_symbol)
        return sorted(list(visited))


def extract_symbol_outline(code: str, filename: str = "snippet.py") -> OutlineResult:
    """Extracts typed function and class skeletons from Python source code without bodies."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return OutlineResult(
            filename=filename,
            total_raw_lines=len(code.splitlines()),
            total_outline_lines=0,
            token_reduction_pct=0.0,
            skeleton_code=f"# SyntaxError parsing {filename}: {e}",
        )

    classes: List[ClassSymbol] = []
    functions: List[FunctionSymbol] = []
    skeleton_lines: List[str] = [f"# Outline: {filename}"]

    def _format_args(args_node: ast.arguments) -> List[str]:
        res = []
        for arg in args_node.args:
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            res.append(f"{arg.arg}{ann}")
        return res

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_async = isinstance(node, ast.AsyncFunctionDef)
            prefix = "async def" if is_async else "def"
            args = _format_args(node.args)
            ret = ast.unparse(node.returns) if node.returns else None
            ret_str = f" -> {ret}" if ret else ""
            doc = ast.get_docstring(node)
            decs = [ast.unparse(d) for d in node.decorator_list]

            for d in decs:
                skeleton_lines.append(f"@{d}")
            skeleton_lines.append(f"{prefix} {node.name}({', '.join(args)}){ret_str}:")
            if doc:
                first_line = doc.strip().splitlines()[0]
                skeleton_lines.append(f'    """{first_line}"""')
            skeleton_lines.append("    ...\n")

            functions.append(
                FunctionSymbol(
                    name=node.name,
                    line_number=node.lineno,
                    is_async=is_async,
                    args=args,
                    return_type=ret,
                    docstring=doc,
                    decorators=decs,
                )
            )

        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            bases_str = f"({', '.join(bases)})" if bases else ""
            doc = ast.get_docstring(node)
            decs = [ast.unparse(d) for d in node.decorator_list]
            methods: List[FunctionSymbol] = []

            for d in decs:
                skeleton_lines.append(f"@{d}")
            skeleton_lines.append(f"class {node.name}{bases_str}:")
            if doc:
                first_line = doc.strip().splitlines()[0]
                skeleton_lines.append(f'    """{first_line}"""')

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_async = isinstance(item, ast.AsyncFunctionDef)
                    prefix = "async def" if is_async else "def"
                    m_args = _format_args(item.args)
                    m_ret = ast.unparse(item.returns) if item.returns else None
                    m_ret_str = f" -> {m_ret}" if m_ret else ""
                    m_doc = ast.get_docstring(item)
                    m_decs = [ast.unparse(d) for d in item.decorator_list]

                    for md in m_decs:
                        skeleton_lines.append(f"    @{md}")
                    skeleton_lines.append(f"    {prefix} {item.name}({', '.join(m_args)}){m_ret_str}:")
                    if m_doc:
                        first_line = m_doc.strip().splitlines()[0]
                        skeleton_lines.append(f'        """{first_line}"""')
                    skeleton_lines.append("        ...\n")

                    methods.append(
                        FunctionSymbol(
                            name=item.name,
                            line_number=item.lineno,
                            is_async=is_async,
                            args=m_args,
                            return_type=m_ret,
                            docstring=m_doc,
                            decorators=m_decs,
                        )
                    )

            if not node.body or not methods:
                skeleton_lines.append("    ...\n")

            classes.append(
                ClassSymbol(
                    name=node.name,
                    line_number=node.lineno,
                    bases=bases,
                    docstring=doc,
                    decorators=decs,
                    methods=methods,
                )
            )

    raw_lines = len(code.splitlines()) or 1
    skeleton_code = "\n".join(skeleton_lines).strip()
    outline_lines = len(skeleton_code.splitlines())
    reduction = max(0.0, round((1.0 - (outline_lines / raw_lines)) * 100, 1))

    return OutlineResult(
        filename=filename,
        total_raw_lines=raw_lines,
        total_outline_lines=outline_lines,
        token_reduction_pct=reduction,
        classes=classes,
        functions=functions,
        skeleton_code=skeleton_code,
    )


def extract_call_graph(code: str, filename: str = "snippet.py") -> CallGraphResult:
    """Builds a directional caller/callee call-graph for functions and methods."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return CallGraphResult(filename=filename, total_symbols=0, nodes={})

    nodes: Dict[str, CallGraphNode] = {}

    # 1. Discover all defined functions & methods
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[node.name] = CallGraphNode(
                symbol_name=node.name,
                defined_at_line=node.lineno,
                callees=[],
                callers=[],
            )

    # 2. Extract calls inside each function
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    callee_name = None
                    if isinstance(sub.func, ast.Name):
                        callee_name = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        callee_name = sub.func.attr
                    if callee_name and callee_name in nodes and callee_name != node.name:
                        if callee_name not in nodes[node.name].callees:
                            nodes[node.name].callees.append(callee_name)
                        if node.name not in nodes[callee_name].callers:
                            nodes[callee_name].callers.append(node.name)

        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in ast.walk(item):
                        if isinstance(sub, ast.Call):
                            callee_name = None
                            if isinstance(sub.func, ast.Name):
                                callee_name = sub.func.id
                            elif isinstance(sub.func, ast.Attribute):
                                callee_name = sub.func.attr
                            if callee_name and callee_name in nodes and callee_name != item.name:
                                if callee_name not in nodes[item.name].callees:
                                    nodes[item.name].callees.append(callee_name)
                                if item.name not in nodes[callee_name].callers:
                                    nodes[callee_name].callers.append(item.name)

    return CallGraphResult(
        filename=filename,
        total_symbols=len(nodes),
        nodes=nodes,
    )
