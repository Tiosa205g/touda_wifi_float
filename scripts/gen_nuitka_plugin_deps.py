"""Scan plugin source files for imports and generate Nuitka --include-package flags.

Usage:
    uv run python scripts/gen_nuitka_plugin_deps.py

Output (stdout): one --include-package=xxx per line
"""

import ast
import os
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
    "urllib3",
    "idna",
}


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
    plugin_imports = scan_plugin_imports(PLUGIN_DIR)

    # 插件在运行时通过 importlib 动态加载，Nuitka 冻结时不会分析这些外部
    # 文件，只会打包从 main.py 可达的模块。因此插件用到的「所有」模块（含
    # 标准库）都必须显式让 Nuitka 打包进来——不能像以前那样减去 stdlib，
    # 否则 concurrent.futures / ctypes 这类仅被插件用到的标准库模块不会被
    # 冻结，运行时就会报 "No module named 'concurrent'"。
    # 主程序已静态引入的第三方包保留在 MAIN_COVERED 中避免重复；src 由主
    # 程序的 --follow-imports 覆盖；plugin_sdk 是运行时松散文件，不进冻结包。
    extra = (
        plugin_imports
        - MAIN_COVERED
        - {"plugin_sdk", "src"}
    )

    # --include-module 对标准库模块和第三方包都适用，且对包会递归包含子模块
    for pkg in sorted(extra):
        print(f"--include-module={pkg}")


if __name__ == "__main__":
    main()
