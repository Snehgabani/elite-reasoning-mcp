"""
Code Analysis Tool — AST-based analysis for build/debug tasks

Uses Python's built-in ast module (no external dependencies).
Provides structural analysis of code for better reasoning.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CodeAnalysis:
    """Result of code analysis."""

    # Basic metrics
    lines_of_code: int
    num_functions: int
    num_classes: int
    num_imports: int

    # Complexity metrics
    avg_function_length: float
    max_function_length: int
    max_nesting_depth: int

    # Structure
    functions: List[Dict]
    classes: List[Dict]
    imports: List[str]

    # Issues
    issues: List[Dict]

    # Summary
    summary: str


class CodeAnalyzer:
    """
    Analyze Python code using AST.

    Usage:
        analyzer = CodeAnalyzer()
        analysis = analyzer.analyze(code_string)

        print(f"Functions: {analysis.num_functions}")
        print(f"Classes: {analysis.num_classes}")
        print(f"Issues: {len(analysis.issues)}")
    """

    def analyze(self, code: str) -> CodeAnalysis:
        """
        Analyze Python code.

        Args:
            code: Python code as string

        Returns:
            CodeAnalysis object
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return CodeAnalysis(
                lines_of_code=len(code.splitlines()),
                num_functions=0,
                num_classes=0,
                num_imports=0,
                avg_function_length=0,
                max_function_length=0,
                max_nesting_depth=0,
                functions=[],
                classes=[],
                imports=[],
                issues=[{"type": "syntax_error", "message": str(e), "line": e.lineno if hasattr(e, "lineno") else 0}],
                summary=f"Syntax error: {e}",
            )

        # Extract information
        functions = self._extract_functions(tree)
        classes = self._extract_classes(tree)
        imports = self._extract_imports(tree)

        # Calculate metrics
        lines_of_code = len(code.splitlines())
        num_functions = len(functions)
        num_classes = len(classes)
        num_imports = len(imports)

        # Function metrics
        func_lengths = [f["length"] for f in functions]
        avg_function_length = sum(func_lengths) / len(func_lengths) if func_lengths else 0
        max_function_length = max(func_lengths) if func_lengths else 0

        # Nesting depth
        max_nesting_depth = self._calculate_max_nesting(tree)

        # Detect issues
        issues = self._detect_issues(tree, functions, classes)

        # Generate summary
        summary = self._generate_summary(
            lines_of_code,
            num_functions,
            num_classes,
            num_imports,
            avg_function_length,
            max_function_length,
            max_nesting_depth,
            issues,
        )

        return CodeAnalysis(
            lines_of_code=lines_of_code,
            num_functions=num_functions,
            num_classes=num_classes,
            num_imports=num_imports,
            avg_function_length=avg_function_length,
            max_function_length=max_function_length,
            max_nesting_depth=max_nesting_depth,
            functions=functions,
            classes=classes,
            imports=imports,
            issues=issues,
            summary=summary,
        )

    def _extract_functions(self, tree: ast.AST) -> List[Dict]:
        """Extract function information."""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate function length
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line
                length = end_line - start_line + 1

                # Count arguments
                num_args = len(node.args.args)

                # Check for docstring
                has_docstring = (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )

                functions.append(
                    {
                        "name": node.name,
                        "line": start_line,
                        "length": length,
                        "num_args": num_args,
                        "has_docstring": has_docstring,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    }
                )

        return functions

    def _extract_classes(self, tree: ast.AST) -> List[Dict]:
        """Extract class information."""
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Count methods
                methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

                # Check for docstring
                has_docstring = (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )

                # Count base classes
                num_bases = len(node.bases)

                classes.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "num_methods": len(methods),
                        "num_bases": num_bases,
                        "has_docstring": has_docstring,
                    }
                )

        return classes

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        return imports

    def _calculate_max_nesting(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth."""
        max_depth = 0

        def visit(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)

            # Increase depth for control flow
            if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                for child in ast.iter_child_nodes(node):
                    visit(child, depth + 1)
            else:
                for child in ast.iter_child_nodes(node):
                    visit(child, depth)

        visit(tree, 0)
        return max_depth

    def _detect_issues(self, tree: ast.AST, functions: List[Dict], classes: List[Dict]) -> List[Dict]:
        """Detect potential issues in code."""
        issues = []

        # Check for long functions
        for func in functions:
            if func["length"] > 50:
                issues.append(
                    {
                        "type": "long_function",
                        "message": f"Function '{func['name']}' is {func['length']} lines long (consider breaking it up)",
                        "line": func["line"],
                        "severity": "warning",
                    }
                )

            if not func["has_docstring"]:
                issues.append(
                    {
                        "type": "missing_docstring",
                        "message": f"Function '{func['name']}' missing docstring",
                        "line": func["line"],
                        "severity": "info",
                    }
                )

        # Check for missing class docstrings
        for cls in classes:
            if not cls["has_docstring"]:
                issues.append(
                    {
                        "type": "missing_docstring",
                        "message": f"Class '{cls['name']}' missing docstring",
                        "line": cls["line"],
                        "severity": "info",
                    }
                )

        # Check for deep nesting
        max_nesting = self._calculate_max_nesting(tree)
        if max_nesting > 4:
            issues.append(
                {
                    "type": "deep_nesting",
                    "message": f"Code has {max_nesting} levels of nesting (consider refactoring)",
                    "line": 0,
                    "severity": "warning",
                }
            )

        return issues

    def _generate_summary(
        self,
        lines_of_code: int,
        num_functions: int,
        num_classes: int,
        num_imports: int,
        avg_function_length: float,
        max_function_length: int,
        max_nesting_depth: int,
        issues: List[Dict],
    ) -> str:
        """Generate human-readable summary."""
        parts = []

        parts.append(f"Code has {lines_of_code} lines")

        if num_functions > 0:
            parts.append(f"{num_functions} functions")

        if num_classes > 0:
            parts.append(f"{num_classes} classes")

        if num_imports > 0:
            parts.append(f"{num_imports} imports")

        if issues:
            warnings = sum(1 for i in issues if i.get("severity") == "warning")
            infos = sum(1 for i in issues if i.get("severity") == "info")
            if warnings > 0:
                parts.append(f"{warnings} warnings")
            if infos > 0:
                parts.append(f"{infos} info messages")

        return ", ".join(parts)


def analyze_code(code: str) -> CodeAnalysis:
    """
    Convenience function to analyze code.

    Args:
        code: Python code as string

    Returns:
        CodeAnalysis object
    """
    analyzer = CodeAnalyzer()
    return analyzer.analyze(code)


if __name__ == "__main__":
    # Test code analyzer
    print("=" * 70)
    print("CODE ANALYSIS TOOL — Testing")
    print("=" * 70)
    print()

    # Test code
    test_code = """
import os
import sys

def hello(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello, {name}!"

def long_function():
    # This function is intentionally long
    x = 1
    y = 2
    z = x + y
    if z > 0:
        for i in range(10):
            if i % 2 == 0:
                print(i)
    return z

class MyClass:
    def method1(self):
        pass
    
    def method2(self):
        pass
"""

    print("Analyzing test code...")
    analysis = analyze_code(test_code)

    print(f"\nSummary: {analysis.summary}")
    print(f"Lines of code: {analysis.lines_of_code}")
    print(f"Functions: {analysis.num_functions}")
    print(f"Classes: {analysis.num_classes}")
    print(f"Imports: {analysis.num_imports}")
    print(f"Avg function length: {analysis.avg_function_length:.1f} lines")
    print(f"Max function length: {analysis.max_function_length} lines")
    print(f"Max nesting depth: {analysis.max_nesting_depth}")
    print(f"Issues: {len(analysis.issues)}")

    if analysis.issues:
        print("\nIssues:")
        for issue in analysis.issues[:5]:
            print(f"  - {issue['type']}: {issue['message']}")

    print()
    print("=" * 70)
    print("✅ CODE ANALYSIS TOOL TEST COMPLETE")
    print("=" * 70)
