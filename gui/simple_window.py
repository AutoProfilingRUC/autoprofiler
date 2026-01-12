"""
简化的主窗口实现 - 先确保核心功能可用
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
import sys
import subprocess
from pathlib import Path
import json
import traceback

class SimpleProfilerWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoProfiler - Python性能分析工具")
        self.root.geometry("900x700")
        
        # 设置最小大小
        self.root.minsize(700, 500)
        
        # 当前分析的文件
        self.current_file = None
        self.is_analyzing = False
        self.analysis_result = None
        self.stop_requested = False
        
        # 创建界面
        self.create_widgets()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 1. 标题
        title_label = ttk.Label(
            main_frame,
            text="Python性能分析工具",
            font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)
        
        # 2. 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="选择Python文件", padding="10")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        # 文件路径显示
        ttk.Label(file_frame, text="当前文件:").grid(row=0, column=0, sticky=tk.W)
        
        self.file_path_var = tk.StringVar(value="未选择文件")
        file_label = ttk.Label(file_frame, textvariable=self.file_path_var, 
                             foreground="gray", width=60, anchor=tk.W)
        file_label.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # 文件信息标签
        self.file_info_var = tk.StringVar(value="")
        file_info_label = ttk.Label(file_frame, textvariable=self.file_info_var,
                                   foreground="blue", font=("Arial", 9))
        file_info_label.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky=tk.W)
        
        # 3. 控制按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 按钮
        self.select_btn = ttk.Button(button_frame, text="选择文件", 
                                    command=self.select_file, width=12)
        self.select_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.analyze_btn = ttk.Button(button_frame, text="开始分析", 
                                     command=self.start_analysis, width=12, state="disabled")
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="停止", 
                                  command=self.stop_analysis, width=12, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.save_btn = ttk.Button(button_frame, text="保存报告", 
                                  command=self.save_report, width=12, state="disabled")
        self.save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = ttk.Button(button_frame, text="清除", 
                                   command=self.clear_all, width=12)
        self.clear_btn.pack(side=tk.LEFT)
        
        # 4. 进度区域
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="就绪")
        self.progress_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=300)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 5. 报告显示区域
        report_frame = ttk.LabelFrame(main_frame, text="分析报告", padding="5")
        report_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 配置权重
        main_frame.rowconfigure(4, weight=1)
        report_frame.rowconfigure(0, weight=1)
        report_frame.columnconfigure(0, weight=1)
        
        # 创建文本框和滚动条
        text_frame = ttk.Frame(report_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        
        # 垂直滚动条
        self.scrollbar_y = ttk.Scrollbar(text_frame)
        self.scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 水平滚动条
        self.scrollbar_x = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        self.scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 报告文本框
        self.report_text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            yscrollcommand=self.scrollbar_y.set,
            xscrollcommand=self.scrollbar_x.set,
            font=("Courier New", 10),
            bg="#f8f8f8",
            relief=tk.FLAT,
            height=20
        )
        self.report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置滚动条
        self.scrollbar_y.config(command=self.report_text.yview)
        self.scrollbar_x.config(command=self.report_text.xview)
        
        # 6. 状态栏
        self.status_var = tk.StringVar(value="就绪 - 选择Python文件开始分析")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def select_file(self):
        """选择文件对话框"""
        filetypes = [
            ("Python文件", "*.py"),
            ("所有文件", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="选择Python文件",
            filetypes=filetypes
        )
        
        if file_path:
            self.load_file(file_path)
            
    def load_file(self, file_path):
        """加载文件并显示信息"""
        try:
            file_path = Path(file_path)
            
            # 验证文件
            if not file_path.exists():
                messagebox.showerror("错误", "文件不存在")
                return
                
            if file_path.suffix.lower() != '.py':
                response = messagebox.askyesno("确认", 
                    f"选择的文件不是.py扩展名 ({file_path.suffix})。\n确定要分析吗？")
                if not response:
                    return
            
            # 更新当前文件
            self.current_file = file_path
            
            # 更新文件显示
            self.file_path_var.set(str(file_path))
            
            # 显示文件信息
            size = file_path.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
            self.file_info_var.set(f"大小: {size_str}")
            
            # 启用分析按钮
            self.analyze_btn.config(state="normal")
            self.save_btn.config(state="disabled")
            
            # 清空之前的报告
            self.clear_report()
            
            # 更新状态
            self.status_var.set(f"已选择文件: {file_path.name} - 点击'开始分析'")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            
    def clear_report(self):
        """清空报告区域"""
        self.report_text.delete(1.0, tk.END)
        self.save_btn.config(state="disabled")
        
    def start_analysis(self):
        """开始分析"""
        if not self.current_file or self.is_analyzing:
            return
            
        # 检查AutoProfiler是否可用
        if not self.check_autoprofiler():
            return
            
        # 重置停止标志
        self.stop_requested = False
        
        # 更新状态
        self.is_analyzing = True
        self.update_ui_state()
        
        # 清空报告区域
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, f"正在分析: {self.current_file.name}\n")
        self.report_text.insert(tk.END, "="*60 + "\n\n")
        
        # 更新进度条
        self.progress_bar.start(10)  # 10ms间隔
        self.progress_label.config(text="分析中...")
        self.status_var.set(f"正在分析: {self.current_file.name}")
        
        # 在后台线程中运行分析
        self.analysis_thread = threading.Thread(target=self.run_analysis_thread, daemon=True)
        self.analysis_thread.start()
        
    def check_autoprofiler(self):
        """检查AutoProfiler是否可用"""
        try:
            # 检查依赖
            import psutil
            import yaml
            
            # 检查autoprofiler模块
            project_root = Path(__file__).parent.parent
            autoprofiler_path = project_root / "autoprofiler"
            
            if not autoprofiler_path.exists():
                messagebox.showerror("错误", 
                    f"未找到autoprofiler目录: {autoprofiler_path}\n"
                    "请确保在项目根目录运行。")
                return False
                
            # 尝试导入关键模块
            sys.path.insert(0, str(project_root))
            
            # 测试导入
            from autoprofiler.runner import Runner
            from autoprofiler.models import TargetProgram
            
            return True
        except ImportError as e:
            error_msg = f"无法加载AutoProfiler:\n{str(e)}\n\n"
            error_msg += "请确保:\n"
            error_msg += "1. 在项目根目录运行\n"
            error_msg += "2. 已安装依赖: pip install psutil PyYAML\n"
            error_msg += f"3. autoprofiler目录存在: {project_root / 'autoprofiler'}"
            
            messagebox.showerror("错误", error_msg)
            return False
            
    def run_analysis_thread(self):
        """后台线程运行分析"""
        try:
            # 导入AutoProfiler模块
            from autoprofiler.runner import Runner
            from autoprofiler.models import TargetProgram
            from autoprofiler.collectors.psutil_collector import PsutilCollector
            from autoprofiler.collectors.cprofile_collector import CProfileCollector
            
            # 检查是否要停止
            if self.stop_requested:
                self.root.after(0, self.analysis_stopped)
                return
            
            # 构建目标程序
            target = TargetProgram(
                command=["python", str(self.current_file)],
                timeout=30,
                cwd=str(self.current_file.parent)
            )
            
            # 创建收集器
            collectors = [
                PsutilCollector(sample_interval=0.1),
                CProfileCollector(),
            ]
            
            # 运行分析
            runner = Runner()
            session = runner.run(target, collectors=collectors)
            
            # 检查是否要停止
            if self.stop_requested:
                self.root.after(0, self.analysis_stopped)
                return
            
            # 尝试加载模式和生成报告
            try:
                # 尝试导入其他模块
                from autoprofiler.patterns.loader import load_patterns
                from autoprofiler.analyzers.simple_analyzer import PatternMatchingAnalyzer
                from autoprofiler.reporting.reporter import render_markdown
                
                # 加载性能模式
                patterns_file = Path(__file__).parent.parent / "autoprofiler" / "patterns" / "performance.yaml"
                if patterns_file.exists():
                    patterns = load_patterns(patterns_file)
                    analyzer = PatternMatchingAnalyzer(patterns)
                    session.findings = analyzer.analyze(session.artifacts)
                else:
                    session.findings = []
                
                # 生成报告
                report = render_markdown(session)
                
                # 保存结果
                self.analysis_result = {
                    'report': report,
                    'session': session
                }
                
                # 在GUI线程中更新结果
                self.root.after(0, self.analysis_complete)
                
            except ImportError as e:
                # 如果某些模块不可用，生成基本报告
                self.generate_basic_report(session)
                
        except Exception as e:
            # 在GUI线程中显示错误
            error_msg = f"分析失败:\n{str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, self.analysis_failed, error_msg)
            
    def generate_basic_report(self, session):
        """生成基本报告（当某些模块不可用时）"""
        report = f"AutoProfiler 基本分析报告\n"
        report += "="*60 + "\n\n"
        
        report += f"目标程序: {self.current_file.name}\n"
        report += f"运行时长: {session.duration:.2f} 秒\n"
        report += f"退出码: {session.exit_code}\n\n"
        
        if hasattr(session, 'stdout') and session.stdout:
            report += "程序输出:\n"
            report += "-"*40 + "\n"
            report += session.stdout + "\n\n"
            
        if hasattr(session, 'stderr') and session.stderr:
            report += "错误输出:\n"
            report += "-"*40 + "\n"
            report += session.stderr + "\n\n"
            
        if hasattr(session, 'artifacts') and session.artifacts:
            report += "收集的数据:\n"
            report += "-"*40 + "\n"
            for artifact in session.artifacts:
                report += f"收集器: {artifact.collector}\n"
                if hasattr(artifact, 'metrics'):
                    for key, value in artifact.metrics.items():
                        report += f"  {key}: {value}\n"
                report += "\n"
        
        self.analysis_result = {
            'report': report,
            'session': session
        }
        
        self.root.after(0, self.analysis_complete)
            
    def analysis_complete(self):
        """分析完成处理"""
        self.is_analyzing = False
        self.update_ui_state()
        
        # 停止进度条
        self.progress_bar.stop()
        self.progress_label.config(text="分析完成")
        
        if not self.analysis_result:
            self.status_var.set("分析失败: 无结果")
            return
            
        # 显示报告
        self.report_text.delete(1.0, tk.END)
        
        # 添加报告内容
        report = self.analysis_result['report']
        self.report_text.insert(tk.END, report)
        
        # 滚动到顶部
        self.report_text.see("1.0")
        
        # 启用保存按钮
        self.save_btn.config(state="normal")
        
        # 更新状态
        self.status_var.set("分析完成 - 点击'保存报告'保存结果")
        
        # 显示完成提示
        messagebox.showinfo("完成", "分析完成！")
        
    def analysis_failed(self, error_msg):
        """分析失败处理"""
        self.is_analyzing = False
        self.update_ui_state()
        
        # 停止进度条
        self.progress_bar.stop()
        self.progress_label.config(text="分析失败")
        
        # 显示错误信息（只显示前500个字符）
        short_error = error_msg[:500] + ("..." if len(error_msg) > 500 else "")
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, f"分析失败:\n{short_error}")
        
        # 更新状态
        self.status_var.set("分析失败")
        
        messagebox.showerror("错误", f"分析失败:\n{short_error}")
        
    def analysis_stopped(self):
        """分析被停止"""
        self.is_analyzing = False
        self.update_ui_state()
        
        self.progress_bar.stop()
        self.progress_label.config(text="已停止")
        self.status_var.set("分析已停止")
        
        messagebox.showinfo("提示", "分析已停止")
        
    def stop_analysis(self):
        """停止分析"""
        if self.is_analyzing:
            self.stop_requested = True
            self.status_var.set("正在停止分析...")
            
    def save_report(self):
        """保存报告"""
        if not self.current_file or not self.analysis_result:
            return
            
        # 获取报告内容
        report_content = self.report_text.get(1.0, tk.END)
        
        if not report_content.strip():
            messagebox.showwarning("警告", "没有报告内容可保存")
            return
            
        # 设置默认文件名
        default_name = f"{self.current_file.stem}_profile_report.md"
        
        # 保存文件对话框
        file_path = filedialog.asksaveasfilename(
            title="保存报告",
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[
                ("Markdown文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                    
                messagebox.showinfo("成功", f"报告已保存到:\n{file_path}")
                self.status_var.set(f"报告已保存: {Path(file_path).name}")
                
            except Exception as e:
                messagebox.showerror("错误", f"保存失败:\n{str(e)}")
                
    def clear_all(self):
        """清除所有内容"""
        if self.is_analyzing:
            response = messagebox.askyesno(
                "确认",
                "分析正在进行中，确定要清除所有内容吗？"
            )
            if not response:
                return
                
            self.stop_analysis()
            
        # 重置状态
        self.current_file = None
        self.is_analyzing = False
        self.analysis_result = None
        self.stop_requested = False
        
        # 更新UI
        self.update_ui_state()
        
        # 清空文件显示
        self.file_path_var.set("未选择文件")
        self.file_info_var.set("")
        
        # 清空报告
        self.clear_report()
        
        # 重置进度条
        self.progress_bar.stop()
        self.progress_label.config(text="就绪")
        
        # 更新状态栏
        self.status_var.set("就绪 - 选择Python文件开始分析")
        
    def update_ui_state(self):
        """根据当前状态更新UI"""
        if self.is_analyzing:
            # 分析进行中
            self.select_btn.config(state="disabled")
            self.analyze_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.save_btn.config(state="disabled")
            self.clear_btn.config(state="disabled")
        else:
            # 分析未进行
            self.select_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.clear_btn.config(state="normal")
            
            # 根据是否有文件决定分析按钮状态
            if self.current_file:
                self.analyze_btn.config(state="normal")
            else:
                self.analyze_btn.config(state="disabled")
                
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.is_analyzing:
            response = messagebox.askyesno("确认", 
                "分析正在进行中，确定要退出吗？")
            if not response:
                return
        
        self.root.destroy()