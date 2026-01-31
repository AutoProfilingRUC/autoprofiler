"""
代码分析器 - 白盒代码分析
"""
import ast
import os
from pathlib import Path
from datetime import datetime

class CodeAnalyzer:
    """白盒代码分析器"""
    
    @staticmethod
    def analyze_code_structure(file_path):
        """分析代码结构"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            # 使用AST分析代码结构
            tree = ast.parse(code_content)
            
            analysis = {
                'basic_info': CodeAnalyzer._get_basic_info(tree, file_path),
                'functions': CodeAnalyzer._analyze_functions(tree),
                'classes': CodeAnalyzer._analyze_classes(tree),
                'imports': CodeAnalyzer._analyze_imports(tree),
                'complexity': CodeAnalyzer._analyze_complexity(tree),
                'issues': CodeAnalyzer._detect_issues(tree),
                'suggestions': []
            }
            
            # 生成代码结构摘要
            analysis['summary'] = CodeAnalyzer._generate_summary(analysis)
            
            return analysis
        except Exception as e:
            return {'error': f'代码分析失败: {str(e)}'}
    
    @staticmethod
    def _get_basic_info(tree, file_path):
        """获取基本信息"""
        file_path_obj = Path(file_path)
        try:
            total_lines = len(file_path_obj.read_text().splitlines())
        except:
            total_lines = 0
            
        return {
            'filename': file_path_obj.name,
            'file_size': file_path_obj.stat().st_size,
            'total_lines': total_lines,
            'code_lines': sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Expr))),
            'analysis_time': datetime.now().isoformat()
        }
    
    @staticmethod
    def _analyze_functions(tree):
        """分析函数"""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func = {
                    'name': node.name,
                    'lineno': node.lineno,
                    'args': len(node.args.args),
                    'has_docstring': ast.get_docstring(node) is not None,
                    'has_decorators': len(node.decorator_list) > 0,
                    'calls': []
                }
                
                # 分析函数内部调用
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Call):
                        if isinstance(subnode.func, ast.Name):
                            func['calls'].append(subnode.func.id)
                
                functions.append(func)
        return functions
    
    @staticmethod
    def _analyze_classes(tree):
        """分析类"""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls = {
                    'name': node.name,
                    'lineno': node.lineno,
                    'methods': [],
                    'bases': [base.id if isinstance(base, ast.Name) else str(base) 
                             for base in node.bases],
                    'has_docstring': ast.get_docstring(node) is not None
                }
                
                # 分析类方法
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        cls['methods'].append(item.name)
                
                classes.append(cls)
        return classes
    
    @staticmethod
    def _analyze_imports(tree):
        """分析导入语句"""
        imports = {'simple': [], 'from_import': []}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports['simple'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports['from_import'].append(f"{module}.{alias.name}")
        return imports
    
    @staticmethod
    def _analyze_complexity(tree):
        """分析复杂度"""
        # 简单复杂度分析
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        
        total_statements = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Expr))
        
        return {
            'function_count': len(functions),
            'class_count': len(classes),
            'avg_function_length': total_statements / len(functions) if functions else 0,
            'max_nested_depth': CodeAnalyzer._get_max_nested_depth(tree)
        }
    
    @staticmethod
    def _get_max_nested_depth(tree):
        """获取最大嵌套深度"""
        max_depth = 0
        
        def visit_node(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, 
                                     ast.FunctionDef, ast.ClassDef)):
                    visit_node(child, depth + 1)
                else:
                    visit_node(child, depth)
        
        visit_node(tree, 0)
        return max_depth
    
    @staticmethod
    def _detect_issues(tree):
        """检测常见问题"""
        issues = []
        
        # 检测过长的函数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                if func_lines > 50:
                    issues.append({
                        'type': 'long_function',
                        'message': f'函数 {node.name} 过长 ({func_lines} 行)',
                        'lineno': node.lineno,
                        'severity': 'warning'
                    })
        
        return issues
    
    @staticmethod
    def _generate_summary(analysis):
        """生成摘要"""
        func_count = len(analysis['functions'])
        class_count = len(analysis['classes'])
        issue_count = len(analysis['issues'])
        
        return f"代码分析完成: {func_count} 个函数, {class_count} 个类, 发现 {issue_count} 个潜在问题"