"""Scan plugin source files for imports and generate Nuitka --include-package flags.

Usage:
    uv run python scripts/gen_nuitka_plugin_deps.py

Output (stdout): one --include-package=xxx per line
"""

import ast
import os
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"

# 主程序已静态 import 的包，Nuitka --follow-imports 会自动覆盖
MAIN_COVERED = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "pluggy",
    "tomlkit",
    "requests",
    "lxml",
    "pyotp",
    "py_mini_racer",
    "urllib3",
    "idna",
}


def get_stdlib() -> frozenset[str]:
    """Return frozenset of stdlib module names (Python 3.10+)."""
    return sys.stdlib_module_names


def scan_plugin_imports(plugin_dir: Path) -> set[str]:
    """Scan all .py files under plugin_dir for top-level imports."""
    imports: set[str] = set()

    for root, _dirs, files in os.walk(plugin_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            try:
                tree = ast.parse(fpath.read_text(encoding="utf-8"))
            except SyntaxError:
                # 跳过语法有问题的文件
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        imports.add(top)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split(".")[0]
                        imports.add(top)

    return imports


def main():
    stdlib = get_stdlib()

    plugin_imports = scan_plugin_imports(PLUGIN_DIR)

    # 只保留插件特有、不在 stdlib 且不在主程序覆盖范围里的包
    extra = (
        plugin_imports
        - stdlib
        - MAIN_COVERED
        - {"plugin_sdk"}  # 项目内模块，不需要 include-package
    )

    for pkg in sorted(extra):
        print(f"--include-package={pkg}")


if __name__ == "__main__":
    main()
