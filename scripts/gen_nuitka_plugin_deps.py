"""Scan plugin source files for imports and generate Nuitka --include-package flags.

Usage:
    uv run python scripts/gen_nuitka_plugin_deps.py

Output (stdout): one Nuitka include flag per line — packages as
    --include-package=xxx, single-file modules as --include-module=xxx.
"""

import ast
import importlib.util
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
    """Scan all .py files under plugin_dir for full dotted import names.

    保留完整点分名（如 concurrent.futures），不要只取顶层名——Nuitka 的
    --include-module 需要完整子包名才能递归打包该子包。
    """
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
                        imports.add(alias.name)  # 完整名：concurrent.futures
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)  # 完整名：PySide6.QtWidgets

    return imports


def _is_package(mod: str) -> bool:
    """判断完整点分名指向的是「包」还是「单个模块文件」。

    Nuitka 对包必须用 --include-package（递归包含），对单文件模块才用
    --include-module（否则包内子模块不会被冻结进 exe，运行时会报
    No module named 'xxx'）。这里用 importlib 的 spec 判定：
    submodule_search_locations 非空即为包。
    """
    try:
        spec = importlib.util.find_spec(mod)
    except (ImportError, ValueError, ModuleNotFoundError):
        return False
    if spec is None:
        return False
    return spec.submodule_search_locations is not None


def main():
    plugin_imports = scan_plugin_imports(PLUGIN_DIR)

    # 按「顶层包名」过滤：主程序已静态引入的第三方包、运行时松散文件不进冻结包。
    # 其余模块（含标准库子包）保留完整点分名，确保 Nuitka 递归包含子模块。
    extra: set[str] = set()
    for mod in plugin_imports:
        top = mod.split(".")[0]
        if top in MAIN_COVERED or top in ("plugin_sdk", "src"):
            continue
        extra.add(mod)

    # 插件运行时通过 importlib 动态加载，Nuitka 不分析这些外部文件，因此插件
    # 用到的「所有」模块都必须显式打包。包用 --include-package（递归冻结整包
    # 及其子模块，例如 concurrent.futures / bs4），单文件模块用 --include-module。
    for pkg in sorted(extra):
        if _is_package(pkg):
            print(f"--include-package={pkg}")
        else:
            print(f"--include-module={pkg}")


if __name__ == "__main__":
    main()
