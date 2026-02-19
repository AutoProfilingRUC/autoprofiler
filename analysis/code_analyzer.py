"""
Code analyzer for single-file whitebox analysis.

Supports:
- Python AST-based analysis
- Multi-language heuristic static analysis
"""
import ast
import re
from datetime import datetime
from pathlib import Path


LANGUAGE_BY_EXT = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
}


FUNCTION_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
    re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_]\w*)\s*\(([^)]*)\)"),
    re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"),
    re.compile(
        r"^\s*(?:(?:public|private|protected|internal|static|final|virtual|override|inline|extern|async)\s+)+[\w<>\[\],\s:*&]+\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(?:\{|=>)"
    ),
]

CLASS_PATTERNS = [
    re.compile(
        r"^\s*(?:export\s+)?(?:(?:public|private|protected|internal|abstract|final)\s+)*class\s+([A-Za-z_]\w*)"
    ),
    re.compile(r"^\s*struct\s+([A-Za-z_]\w*)"),
]

IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+(.+)$"),
    re.compile(r"^\s*from\s+(.+)\s+import\s+(.+)$"),
    re.compile(r"^\s*#include\s+(.+)$"),
    re.compile(r"^\s*use\s+(.+)$"),
    re.compile(r"^\s*require\s*\((.+)\)"),
]


class CodeAnalyzer:
    """Whitebox code analyzer."""

    @staticmethod
    def detect_language(file_path) -> str:
        p = Path(file_path)
        return LANGUAGE_BY_EXT.get(p.suffix.lower(), "unknown")

    @staticmethod
    def is_supported_file(file_path) -> bool:
        p = Path(file_path)
        return p.suffix.lower() in LANGUAGE_BY_EXT

    @staticmethod
    def supported_extensions():
        return sorted(LANGUAGE_BY_EXT.keys())

    @staticmethod
    def analyze_code_structure(file_path):
        """Analyze code structure with language-specific strategy."""
        try:
            path_obj = Path(file_path)
            code_content = path_obj.read_text(encoding="utf-8", errors="ignore")
            language = CodeAnalyzer.detect_language(path_obj)

            if language == "python":
                return CodeAnalyzer._analyze_python_structure(path_obj, code_content)
            return CodeAnalyzer._analyze_generic_structure(path_obj, code_content, language)
        except Exception as err:
            return {"error": f"代码分析失败: {err}"}

    @staticmethod
    def _get_basic_info(file_path: Path, code_content: str, language: str) -> dict:
        lines = code_content.splitlines()
        return {
            "filename": file_path.name,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "total_lines": len(lines),
            "code_lines": sum(
                1 for line in lines if line.strip() and not line.strip().startswith(("#", "//", "/*", "*"))
            ),
            "analysis_time": datetime.now().isoformat(),
            "language": language,
        }

    @staticmethod
    def _analyze_python_structure(file_path: Path, code_content: str) -> dict:
        tree = ast.parse(code_content)
        analysis = {
            "basic_info": CodeAnalyzer._get_basic_info(file_path, code_content, "python"),
            "functions": CodeAnalyzer._analyze_python_functions(tree),
            "classes": CodeAnalyzer._analyze_python_classes(tree),
            "imports": CodeAnalyzer._analyze_python_imports(tree),
            "complexity": CodeAnalyzer._analyze_python_complexity(tree),
            "issues": CodeAnalyzer._detect_python_issues(tree, code_content),
            "performance_signals": CodeAnalyzer._detect_performance_signals(code_content, "python"),
            "suggestions": [],
            "analysis_mode": "python_ast",
        }
        analysis["summary"] = CodeAnalyzer._generate_summary(analysis)
        return analysis

    @staticmethod
    def _analyze_generic_structure(file_path: Path, code_content: str, language: str) -> dict:
        functions = CodeAnalyzer._analyze_generic_functions(code_content)
        classes = CodeAnalyzer._analyze_generic_classes(code_content)
        complexity = CodeAnalyzer._analyze_generic_complexity(code_content)
        issues = CodeAnalyzer._detect_generic_issues(code_content, complexity, functions)
        analysis = {
            "basic_info": CodeAnalyzer._get_basic_info(file_path, code_content, language),
            "functions": functions,
            "classes": classes,
            "imports": CodeAnalyzer._analyze_generic_imports(code_content),
            "complexity": complexity,
            "issues": issues,
            "performance_signals": CodeAnalyzer._detect_performance_signals(code_content, language),
            "suggestions": [],
            "analysis_mode": "generic_static",
        }
        analysis["summary"] = CodeAnalyzer._generate_summary(analysis)
        return analysis

    @staticmethod
    def _analyze_python_functions(tree):
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": len(getattr(node.args, "args", [])),
                    "has_docstring": ast.get_docstring(node) is not None,
                    "has_decorators": len(getattr(node, "decorator_list", [])) > 0,
                    "calls": [],
                }
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Call) and isinstance(subnode.func, ast.Name):
                        func["calls"].append(subnode.func.id)
                functions.append(func)
        return functions

    @staticmethod
    def _analyze_python_classes(tree):
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": [],
                    "bases": [
                        base.id if isinstance(base, ast.Name) else str(base)
                        for base in getattr(node, "bases", [])
                    ],
                    "has_docstring": ast.get_docstring(node) is not None,
                }
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        cls["methods"].append(item.name)
                classes.append(cls)
        return classes

    @staticmethod
    def _analyze_python_imports(tree):
        imports = {"simple": [], "from_import": []}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports["simple"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports["from_import"].append(f"{module}.{alias.name}".strip("."))
        return imports

    @staticmethod
    def _analyze_python_complexity(tree):
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        return {
            "function_count": len(functions),
            "class_count": len(classes),
            "max_nested_depth": CodeAnalyzer._max_nested_depth_ast(tree),
            "branch_count": sum(
                1
                for n in ast.walk(tree)
                if isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.Match))
            ),
        }

    @staticmethod
    def _max_nested_depth_ast(tree):
        max_depth = 0

        def visit(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.FunctionDef, ast.ClassDef)):
                    visit(child, depth + 1)
                else:
                    visit(child, depth)

        visit(tree, 0)
        return max_depth

    @staticmethod
    def _detect_python_issues(tree, code_content: str):
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", None)
                func_lines = (end_lineno - node.lineno) if end_lineno else 0
                if func_lines > 80:
                    issues.append(
                        {
                            "type": "long_function",
                            "message": f"函数 {node.name} 过长 ({func_lines} 行)",
                            "lineno": node.lineno,
                            "severity": "warning",
                        }
                    )
        for idx, line in enumerate(code_content.splitlines(), start=1):
            if len(line) > 140:
                issues.append(
                    {
                        "type": "long_line",
                        "message": f"第 {idx} 行过长 ({len(line)} 字符)",
                        "lineno": idx,
                        "severity": "info",
                    }
                )
        return issues[:80]

    @staticmethod
    def _analyze_generic_functions(code_content: str):
        functions = []
        for lineno, raw_line in enumerate(code_content.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            for pattern in FUNCTION_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue
                name = match.group(1)
                args_raw = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
                arg_count = 0
                if args_raw.strip():
                    arg_count = len([a for a in args_raw.split(",") if a.strip()])
                functions.append(
                    {
                        "name": name,
                        "lineno": lineno,
                        "args": arg_count,
                        "has_docstring": False,
                        "has_decorators": False,
                        "calls": [],
                    }
                )
                break
        return functions

    @staticmethod
    def _analyze_generic_classes(code_content: str):
        classes = []
        for lineno, raw_line in enumerate(code_content.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            for pattern in CLASS_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue
                classes.append(
                    {
                        "name": match.group(1),
                        "lineno": lineno,
                        "methods": [],
                        "bases": [],
                        "has_docstring": False,
                    }
                )
                break
        return classes

    @staticmethod
    def _analyze_generic_imports(code_content: str):
        imports = {"simple": [], "from_import": []}
        for raw_line in code_content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("from ") and " import " in line:
                imports["from_import"].append(line)
                continue
            for pattern in IMPORT_PATTERNS:
                if pattern.match(line):
                    imports["simple"].append(line)
                    break
        return imports

    @staticmethod
    def _analyze_generic_complexity(code_content: str):
        text = code_content.lower()
        branch_count = len(re.findall(r"\b(if|else if|switch|case|match|when|try|catch)\b", text))
        loop_count = len(re.findall(r"\b(for|while|foreach|loop)\b", text))
        return {
            "function_count": len(CodeAnalyzer._analyze_generic_functions(code_content)),
            "class_count": len(CodeAnalyzer._analyze_generic_classes(code_content)),
            "max_nested_depth": CodeAnalyzer._max_brace_depth(code_content),
            "branch_count": branch_count,
            "loop_count": loop_count,
        }

    @staticmethod
    def _max_brace_depth(code_content: str):
        depth = 0
        max_depth = 0
        for ch in code_content:
            if ch == "{":
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == "}":
                depth = max(0, depth - 1)
        return max_depth

    @staticmethod
    def _detect_generic_issues(code_content: str, complexity: dict, functions: list):
        issues = []
        lines = code_content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if len(line) > 160:
                issues.append(
                    {
                        "type": "long_line",
                        "message": f"Line {idx} is very long ({len(line)} chars)",
                        "lineno": idx,
                        "severity": "info",
                    }
                )
            if "todo" in line.lower() or "fixme" in line.lower():
                issues.append(
                    {
                        "type": "todo_marker",
                        "message": f"Line {idx} contains TODO/FIXME",
                        "lineno": idx,
                        "severity": "info",
                    }
                )
        if complexity.get("max_nested_depth", 0) >= 6:
            issues.append(
                {
                    "type": "high_nesting",
                    "message": f"Nested block depth is high ({complexity.get('max_nested_depth')})",
                    "lineno": 1,
                    "severity": "warning",
                }
            )
        if len(functions) >= 120:
            issues.append(
                {
                    "type": "too_many_functions",
                    "message": f"Function count is high ({len(functions)})",
                    "lineno": 1,
                    "severity": "warning",
                }
            )
        return issues[:80]

    @staticmethod
    def _detect_performance_signals(code_content: str, language: str):
        text = code_content.lower()
        loop_positions = [m.start() for m in re.finditer(r"\b(for|while|foreach|loop)\b", text)]
        nested_loop_suspected = False
        for i in range(len(loop_positions) - 1):
            if loop_positions[i + 1] - loop_positions[i] < 300:
                nested_loop_suspected = True
                break
        return {
            "language": language,
            "nested_loop_suspected": nested_loop_suspected,
            "io_keyword_hits": len(
                re.findall(r"\b(read|write|open|fstream|ifstream|ofstream|file\.|fs\.)\b", text)
            ),
            "db_keyword_hits": len(
                re.findall(r"\b(select|insert|update|delete|cursor|executequery|executenonquery)\b", text)
            ),
            "network_keyword_hits": len(
                re.findall(r"\b(http|https|request|fetch|axios|socket|grpc|rest)\b", text)
            ),
            "concurrency_keyword_hits": len(
                re.findall(r"\b(thread|async|await|lock|mutex|channel|goroutine|task)\b", text)
            ),
        }

    @staticmethod
    def _generate_summary(analysis):
        basic = analysis.get("basic_info", {})
        func_count = len(analysis.get("functions", []))
        class_count = len(analysis.get("classes", []))
        issue_count = len(analysis.get("issues", []))
        language = basic.get("language", "unknown")
        return f"{language} 代码分析完成: {func_count} 个函数, {class_count} 个类型, 发现 {issue_count} 个潜在问题"
