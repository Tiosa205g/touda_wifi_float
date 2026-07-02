# 更新日志

## [v1.4.7.1] - 2026-07-02

### 🆕 新功能
- 版本检查：启动时自动检测 GitHub 新版本并弹窗通知
- 统一弹窗组件 `FramelessDialog`，插件和系统使用统一风格弹窗
- 插件 SDK 新增 `show_message()` / `show_confirm()` / `show_input_list()` 弹窗接口

### 🎨 优化
- 优化主题切换逻辑，修复部分控件主题不跟随切换的问题

### 🐛 修复
- 修复 B 站直播解析插件在链接无法解析时只有日志没有弹窗提示的问题

### 📦 变更
- 新增 `src/update_checker.py` 模块
- 新增 `ui/components/frameless_dialog.py` 组件
- 重构 `plugins/plugin_sdk.py`，整合弹窗功能到 SDK 基类
