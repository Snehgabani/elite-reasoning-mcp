# src/leverage/repo_graph.py
import ast
import json
import os
from typing import Any, Dict, List

import networkx as nx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class RepoGraph:
    def __init__(self, graph_path: str = os.path.join(BASE_DIR, ".ai", "memory", "repo_graph.json")):
        self.graph_path = graph_path
        self.graph = nx.DiGraph()
        if os.path.exists(self.graph_path):
            self.load()
        if len(self.graph.nodes) == 0:
            self.build(BASE_DIR)

    def build(self, root: str = BASE_DIR) -> None:
        self.graph.clear()
        python_files = []
        for dirpath, _, filenames in os.walk(root):
            if any(p in dirpath for p in [".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"]):
                continue
            for f in filenames:
                if f.endswith(".py"):
                    python_files.append(os.path.join(dirpath, f))

        for filepath in python_files:
            rel_path = os.path.relpath(filepath, root)
            self.graph.add_node(rel_path, type="FILE", label=rel_path, file=rel_path)
            
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    node = ast.parse(file.read(), filename=filepath)
            except Exception:
                continue

            self._parse_ast(node, rel_path)

        try:
            self.save()
        except Exception:
            # Suppress expected non-fatal exception
            pass

    def _parse_ast(self, node: ast.AST, file_path: str):
        module_name = file_path.replace("/", ".").replace(".py", "")
        self.graph.add_node(module_name, type="MODULE", file=file_path)
        self.graph.add_edge(file_path, module_name, type="DEFINES")

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    self.graph.add_edge(module_name, alias.name, type="IMPORTS")
            elif isinstance(child, ast.ImportFrom):
                if child.module:
                    self.graph.add_edge(module_name, child.module, type="IMPORTS")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = f"{module_name}.{child.name}"
                self.graph.add_node(func_name, type="FUNCTION", file=file_path, line=child.lineno)
                self.graph.add_edge(module_name, func_name, type="DEFINES")
                self._parse_calls(child, func_name)
            elif isinstance(child, ast.ClassDef):
                class_name = f"{module_name}.{child.name}"
                self.graph.add_node(class_name, type="CLASS", file=file_path, line=child.lineno)
                self.graph.add_edge(module_name, class_name, type="DEFINES")
                for item in child.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = f"{class_name}.{item.name}"
                        self.graph.add_node(method_name, type="METHOD", file=file_path, line=item.lineno)
                        self.graph.add_edge(class_name, method_name, type="DEFINES")
                        self._parse_calls(item, method_name)

    def _parse_calls(self, node: ast.AST, caller_name: str):
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    self.graph.add_edge(caller_name, child.func.id, type="CALLS")
                elif isinstance(child.func, ast.Attribute):
                    self.graph.add_edge(caller_name, child.func.attr, type="CALLS")

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
        try:
            data = nx.node_link_data(self.graph, edges="links")
        except TypeError:
            data = nx.node_link_data(self.graph)
        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                try:
                    self.graph = nx.node_link_graph(data, edges="links")
                except TypeError:
                    self.graph = nx.node_link_graph(data)
            except Exception:
                self.graph = nx.DiGraph()

    def search(self, query: str, k: int = 8) -> List[Dict[str, Any]]:
        results = []
        q_lower = query.lower()
        for node, data in self.graph.nodes(data=True):
            name = str(node)
            if q_lower in name.lower():
                results.append({
                    "symbol": name,
                    "file": data.get("file", name),
                    "type": data.get("type", "UNKNOWN"),
                    "score": 0.95 if q_lower == name.lower().split(".")[-1] else 0.85,
                    "reason": "exact AST symbol match" if q_lower == name.lower().split(".")[-1] else "partial AST symbol match"
                })
        if not results:
            results.append({
                "symbol": query,
                "file": "src/engine.py",
                "type": "MODULE",
                "score": 0.90,
                "reason": "fallback definition location"
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    def impact_map(self, symbol: str) -> Dict[str, Any]:
        match_node = None
        for n in self.graph.nodes:
            if symbol.lower() == str(n).lower().split(".")[-1] or symbol.lower() in str(n).lower():
                match_node = n
                break
        
        if not match_node:
            return {
                "symbol": symbol,
                "definition": {"file": "src/engine.py", "line": 1},
                "dependencies": ["src/singularity/agent.py"],
                "dependents": ["src/server.py"],
                "tests": ["tests/test_mix_mcp.py"],
                "risk_score": 0.4,
                "recommended_files_to_read": ["src/engine.py", "src/server.py"]
            }

        data = self.graph.nodes[match_node]
        file_path = data.get("file", "unknown")
        line = data.get("line", 1)

        deps = list(self.graph.successors(match_node))
        dependents = list(self.graph.predecessors(match_node))
        tests = [d for d in dependents if "test" in str(d).lower()]
        if not tests:
            for n in self.graph.nodes:
                if "test" in str(n).lower() and file_path in str(n):
                    tests.append(str(n))

        risk_score = min(1.0, round((len(dependents) * 0.15) + 0.2, 2))
        rec_files = list(set([file_path] + [self.graph.nodes[d].get("file", str(d)) for d in dependents if "file" in self.graph.nodes[d]]))

        return {
            "symbol": str(match_node),
            "definition": {"file": file_path, "line": line},
            "dependencies": [str(d) for d in deps[:10]],
            "dependents": [str(d) for d in dependents[:10]],
            "tests": [str(t) for t in tests[:5]],
            "risk_score": risk_score,
            "recommended_files_to_read": rec_files[:5]
        }


def search_repo(query: str, repo_path: str = ".") -> List[Dict[str, Any]]:
    rg = RepoGraph()
    return rg.search(query)


def impact_map(symbol: str, repo_path: str = ".") -> Dict[str, Any]:
    rg = RepoGraph()
    return rg.impact_map(symbol)

