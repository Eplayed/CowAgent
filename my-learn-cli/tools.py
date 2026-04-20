"""
工具定义 — 对应 CowAgent 的 agent/tools/ 目录

CowAgent 手写了 BaseTool 基类 + 十几个工具类，
LangChain 用 @tool 装饰器几行就能定义一个工具。

对应关系：
- bash_run()      → CowAgent 的 agent/tools/bash/bash.py
- read_file()     → CowAgent 的 agent/tools/read/read.py
- list_directory() → CowAgent 的 agent/tools/ls/ls.py
"""

import subprocess
import os
from langchain_core.tools import tool


@tool
def bash_run(command: str) -> str:
    """执行 shell 命令并返回输出结果。用于运行系统命令、查看进程、安装软件等。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code]: {result.returncode}"
        return output.strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        return "命令执行超时（30秒限制）"
    except Exception as e:
        return f"执行失败: {e}"


@tool
def read_file(path: str) -> str:
    """读取指定路径的文件内容。用于查看代码、配置文件、日志等。"""
    try:
        path = os.path.expanduser(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 5000:
            content = content[:5000] + f"\n\n... (文件过长，已截断，共 {len(content)} 字符)"
        return content
    except FileNotFoundError:
        return f"文件不存在: {path}"
    except Exception as e:
        return f"读取失败: {e}"


@tool
def list_directory(path: str = ".") -> str:
    """列出目录下的文件和文件夹。用于查看项目结构、查找文件等。"""
    try:
        path = os.path.expanduser(path)
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                result.append(f"📁 {entry}/")
            else:
                size = os.path.getsize(full_path)
                result.append(f"📄 {entry} ({size} bytes)")
        return "\n".join(result) or "(空目录)"
    except FileNotFoundError:
        return f"目录不存在: {path}"
    except Exception as e:
        return f"列出失败: {e}"


# 所有工具列表，方便导入
ALL_TOOLS = [bash_run, read_file, list_directory]
