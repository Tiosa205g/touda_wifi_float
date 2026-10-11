# 更新日志

## [v1.4.7.4] - 2026-10-11

### 🚀 性能优化
- **状态轮询后台线程化**：`Update_timer` 的 `getState()`/`login()` 网络请求移入后台线程执行（原先每个轮询周期最多阻塞 UI 主线程约 15 秒，期间悬浮球无法拖动），并带防重入保护——上一轮未完成时跳过本次轮询而非堆积线程
- **跨线程信号安全化**：`flux_update` 从直连 lambda 改为连接到主线程接收者槽（`FloatBall.on_flux_update`），后台线程发射信号时自动走队列连接，不再在工作线程中操作 UI 控件
- **会话并发保护**：`wifi`/`webvpn` 各增加可重入锁，串行化轮询线程、启动登录线程、切换账号线程对同一 `requests.Session` 的并发访问
- **WebVPN 请求超时补全**：webvpn 登录/状态检查请求补上缺失的超时参数，断网时不再无限挂起

### 🎨 优化
- **右键菜单动态刷新**：菜单框架仍缓存复用（保留防内存增长设计），账号/链接/插件区改为按内容指纹比对刷新——新增账号/链接、切换账号、服务号绑定状态变化后下次右键即可见，不再是首次构建时的永久快照；内容未变时零重建
- **插件菜单加载逻辑重构**：插件子菜单逐个独立隔离（单个插件异常不影响其他插件）、`get_menu()` 返回空值容错、非可调用菜单项安全跳过
- **汕大服务号插件**：登录态查询按账号缓存 180 秒并增加异常保护，构建菜单不再每次同步请求网络（原先最长阻塞 3 秒）；绑定/解绑请求补全超时，成功后自动失效缓存

### 🐛 修复
- **修复右键菜单内存泄漏**：qfluentwidgets 的 `RoundMenu.clear()`/`removeMenu()` 只移除列表引用，不释放子菜单的 QObject 父子关系——动态刷新前显式收集旧子菜单并 `deleteLater`，实测 300 次强制重建对象计数零增长
- 修正 `get_data()` 返回值类型注解（实际返回 `(流量额, 已用, 用户名)` 三元组）

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
