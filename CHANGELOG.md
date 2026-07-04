# 更新日志

## [v1.4.7.2] - 2026-07-04

### 🎨 优化
- 去除 `mini-racer` 库依赖，RSA 加密改用纯 Python 算法实现，减少打包体积
- 优化插件加载逻辑：每个插件独立 try-catch，避免单个插件加载失败导致所有插件无法使用
- 更新检查异常处理重构：网络/HTTP 错误改为抛出自定义 `UpdateCheckError`，不再静默吞异常

### 🐛 修复
- 修复 WebVPN 登录检测逻辑：补充响应长度过短时的判断，避免空响应误判为登录成功
- 修复 WiFi 登录后用户名被 `<UNK>` 覆盖导致凭据被污染的问题（仅当解析出有效用户名时才更新 `self.name`）

### 📦 变更
- 移除 `pyproject.toml` 中 `mini-racer` 依赖项
- 移除 `scripts/gen_nuitka_plugin_deps.py` 中 `py_mini_racer` 覆盖项

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
