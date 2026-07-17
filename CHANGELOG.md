# 更新日志

## [v1.4.7.3] - 2026-07-17

### 🏗 重构
- **移除 `DragWindow` 基类依赖**，`FloatBall` 直接继承 `QWidget`，内联拖拽逻辑与屏幕边缘吸附，减少外部库耦合
- **窗口透明背景优化**：`FloatBall` 增加样式表彻底去除 DWM 框架残留，`WaterBall` 组件增加透明背景属性
- `setupUI()` 中移除 `show()` 调用，窗口显示时机统一由 `FloatBall.__init__` 控制

### 🆕 新功能
- **窗口坐标有效性检查**：启动时验证保存坐标是否在当前屏幕范围内，副屏移除后自动居中到主屏可用区域并记录日志
- **切换 IP 插件**：重写插件（+1134 / -403 行），新增 DDNS 功能支持，功能界面调整

### 🚀 启动优化
- 开机自启模式下同样允许 UAC 提权：移除 `--auto-start` 跳过管理员检查的逻辑
- 开机自启注册表路径中移除 `--auto-start` 参数

### 📦 依赖与构建
- 所有依赖锁定到固定版本（`>=` → `==`），确保可复现构建
- 新增显式依赖：`charset-normalizer`、`pip`、`pyside6-addons`、`pyside6-essentials`、`shiboken6`、`soupsieve`、`typing-extensions`
- **移除本地 `compile.bat` 打包脚本**，统一仅由 GitHub Actions CI 构建
- 更新 `README.md`：删除本地 Nuitka 打包说明
- `.gitignore` 新增 `nuitka_plugin_deps.txt` 忽略规则

### 🐛 修复
- **Nuitka 插件依赖扫描修复**：`gen_nuitka_plugin_deps.py` 区分包（`--include-package`）与模块（`--include-module`），修复 CI 下标准库子包未完整冻结导致插件报 `No module named` 的问题

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
