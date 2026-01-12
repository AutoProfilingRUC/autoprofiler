#!/usr/bin/env python3
"""
AutoProfiler GUI - 简化版本（先解决核心功能）
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """主函数"""
    try:
        # 检查必需依赖
        check_dependencies()
        
        # 导入主窗口
        from gui.simple_window import SimpleProfilerWindow
        
        # 创建主窗口
        root = tk.Tk()
        app = SimpleProfilerWindow(root)
        
        # 启动主循环
        root.mainloop()
        
    except ImportError as e:
        print(f"错误: {e}")
        print("\n请安装必需依赖:")
        print("pip install psutil PyYAML")
        input("按Enter键退出...")
        sys.exit(1)
    except Exception as e:
        print(f"程序错误: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")
        sys.exit(1)

def check_dependencies():
    """检查必需依赖"""
    required = ['psutil', 'yaml']
    missing = []
    
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        raise ImportError(f"缺少必需依赖: {', '.join(missing)}")

if __name__ == "__main__":
    main()