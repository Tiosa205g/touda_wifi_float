# 汕大校园网工具-悬浮球版 🌊

<div align="center">

![Version](https://img.shields.io/badge/version-v1.4.6-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

一款为汕头大学校园网设计的桌面悬浮球工具，集成校园网登录、WebVPN 访问、流量监控与插件扩展等功能。

[功能特性](#功能特性) • [安装](#安装) • [使用说明](#使用说明) • [配置](#配置) • [插件系统](#插件系统) • [开发](#开发)

</div>

---

## 功能特性

### 🌐 校园网管理

- **自动登录**：自动检测登录状态，支持定时自动重连
- **流量监控**：实时显示流量使用情况
- **多账号切换**：支持多账号配置，快速切换登录账号
- **状态显示**：实时查看网络状态和账号信息

### 🔐 WebVPN 功能

- **一键登录**：自动登录汕大 WebVPN，免去传统使用数盾 OTP 进行登录
- **链接转换**：自动将普通链接转换为 WebVPN 链接
- **TWFID 管理**：自动保存和使用 TWFID，免重复登录
- **快捷访问**：预设常用校园链接（教务系统、mystu等），也可自由添加链接

### 🎨 界面特性

- **悬浮球设计**：简约美观的水球进度显示
- **窗口置顶**：始终保持在桌面最前方
- **拖拽移动**：支持自由拖拽，位置自动保存
- **右键菜单**：快捷操作菜单，功能一键可达
- **主题切换**：支持亮色/暗色/自动主题

### 🔗 扩展功能

- **B站直播解析**：支持哔哩哔哩直播链接解析播放
- **自定义链接**：支持添加和管理自定义常用链接
- **剪贴板操作**：快速处理剪贴板中的链接

### 🧩 插件扩展

- **动态插件系统**：支持在 `plugins/` 目录中以子文件夹形式放置插件，运行时自动发现与加载
- **菜单集成**：插件可向悬浮球右键菜单注入自定义子菜单/动作
- **统一钩子接口**：基于 pluggy 的钩子规范，简洁可维护

## 📸 截图展示

> 悬浮球

![悬浮球](/display/悬浮球.png)

> 右键菜单功能

![菜单](/display/右键菜单.png)

> 设置界面
> ![设置](/display/设置界面.png)

## 安装

### 方式一：直接运行（推荐）

1. 从 [Releases](https://github.com/Tiosa205g/touda_wifi_float/releases) 下载最新版本的压缩包并解压到合适位置
2. 双击运行 `main.exe`
3. 首次运行会自动创建配置文件

### 方式二：从源码运行

#### 环境要求

- Python 3.12 或更高版本
- Windows 操作系统
- [uv](https://docs.astral.sh/uv/) 包管理器（推荐）

#### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/Tiosa205g/touda_wifi_float.git
cd touda_wifi_float
```

2. **安装依赖**

```bash
uv sync
```

3. **运行程序**

```bash
uv run python main.py
```

提示：从源码运行若使用插件功能，请确保已安装 pluggy（已包含在项目依赖中，`uv sync` 会自动安装）。

## 配置

程序首次运行会在 `config` 目录下自动创建或补全配置文件：

### 📁 配置文件结构

```
config/
├── main.toml          # 主配置（包含悬浮球位置/定时器/WebVPN 可选项）
├── account_0.toml     # 校园网账号配置（可新增多个 account_N.toml）
└── links.toml         # 自定义链接配置（支持分组）
```

### 🔧 配置说明

#### `main.toml` - 主配置

```toml
[main]
current_account = "0"           # 当前使用的账号索引
x = 1351                        # 悬浮球 X 坐标
y = 138                         # 悬浮球 Y 坐标
timer_interval = 60000          # 自动检测间隔（毫秒）

[ui]
theme = "auto"                  # 主题: auto/light/dark

[webvpn]
# 以下字段为可选项，便于程序自动登录 WebVPN；未填写时可在运行时登录
name = ""                       # WebVPN 用户名（学号）
password = ""                   # WebVPN 密码（Base64 编码存储）
key = ""                        # 数盾 OTP 秘钥（用于生成 6 位口令）
twfid = ""                      # WebVPN TWFID（程序成功登录后会自动写入）
```

#### `account_0.toml` - 账号配置

```toml
[setting]
name = ""                       # 校园网账号
password = ""                   # 校园网密码（Base64编码）
```

#### `links.toml` - 自定义链接

```toml
[汕大]
汕大官网 = "https://www.stu.edu.cn/"
教务系统 = "https://jw.stu.edu.cn/"
mystu = "https://my.stu.edu.cn/"

[常用]
# 添加你的自定义链接
```

### 🔑 配置 WebVPN

1. 运行程序后，找到 `config/main.toml`
2. 填入你的 WebVPN 信息：
   - `name`: 你的学号
   - `password`: 你的密码（使用 Base64 编码）
   - `key`: 数盾 OTP 密钥（如已绑定）

小贴士：出于安全考虑，配置中密码以 Base64 存储，并非加密，仅用于避免明文直观可读。

**Base64 编码密码示例（Python）**：

```python
import base64
password = "your_password"
encoded = base64.b64encode(password.encode()).decode()
print(encoded)  # 将此值填入配置文件
```

## 📖 使用说明

### 基本操作

- **右键悬浮球**：打开功能菜单
- **拖拽悬浮球**：移动位置（自动保存）
- **系统托盘图标**：右键可显示详细信息、打开设置界面、退出程序

### 功能菜单

#### 📱 账号菜单

- 切换已配置的校园网账号
- 支持多个账号快速切换

#### 🔗 链接菜单

- 访问预设的校园常用链接
- 可选择是否通过 WebVPN 访问
- 支持 B站直播链接解析

#### 🌐 WebVPN 菜单

- **剪切板链接**：打开剪贴板中的链接
- **复制一键登录链接**：生成 WebVPN 免密登录链接
- **转换剪贴板链接**：将剪贴板中的链接批量转换为 WebVPN 格式
- **复制6位口令**：复制当前的 OTP 动态口令
- **复制 TWFID**：复制用于登录的 TWFID

#### 🧩 插件菜单（如有插件）

- 加载 `plugins/` 下有效插件后，此菜单会展示插件提供的功能入口
- 每个插件可提供一个或多个动作/子菜单

### 高级功能

#### B站直播解析

1. 复制 B站直播间链接
2. 右键菜单 → 链接 → 剪切板链接
3. 选择"是"使用解析功能
4. 选择解析地址后自动播放（尽量选择特殊的）

#### 链接批量转换

1. 复制包含多个链接的文本到剪贴板
2. 右键菜单 → WebVPN → 转换剪贴板链接
3. 所有链接自动转换为 WebVPN 格式

> tips:可以用来批量解析下载链接

## 插件系统

项目内置基于 pluggy 的插件系统，默认扫描并加载 `plugins/` 目录下的所有子目录，只要该目录中包含 `main.py` 且定义了约定的 `Plugin` 类即可。

### 目录结构（示例）

```
plugins/
  MyPlugin/
    main.py
  另一个插件/
    main.py
```

### 最小可用插件模板

```python
# plugins/Example/main.py
import pluggy
from pathlib import Path

PLUGIN_NAME = '示例插件'
PLUGIN_VERSION = '1.0.0'
PLUGIN_PATH = Path(__file__).parent

# 使用与主程序一致的标识，不可修改
hook = pluggy.HookimplMarker("toudawifi")

class Plugin:  # 类名必须为 Plugin，不可修改
    @hook
    def start(self, api) -> bool:
        """插件加载时调用，返回 True 代表加载成功"""
        self.api = api
        # 可使用 api.wifi / api.webvpn 进行业务操作
        return True

    @hook
    def get_name(self) -> str:
        return PLUGIN_NAME

    @hook
    def get_description(self) -> str:
        return "一个最小可用的示例插件。"

    @hook
    def get_menu(self) -> list[dict]:
        # 在悬浮球菜单中添加一个动作
        return [{
            'function': '示例动作',
            'object': self.on_click
        }]

    def on_click(self):
        self.api.logger.info("示例动作被点击")

    # 可选钩子：on_setting / on_disable / on_exit
```

### 可用 API（注入给插件的 api 对象）

- `api.wifi`: 已实例化的校园网对象，支持登录、获取状态等
- `api.webvpn`: 已实例化的 WebVPN 对象，支持自动登录、链接转换等
- `api.cfg`: `CfgParse` 类（用于读取/写入插件自有配置）
- `api.VERSION`: 主程序版本号
- `api.CFG_DIR` / `api.MAIN_CFG` / `api.LINKS_CFG`: 配置目录与核心配置文件路径
- `api.logger`: 日志记录器
- `api.app`: QApplication 实例
- `api.parent`: 悬浮球主窗口对象

注意：插件应当做好异常处理，避免阻塞 UI 线程；可结合线程/异步在合适的线程中执行耗时任务。

### 内置插件

| 插件 | 说明 |
|------|------|
| `example` | 示例插件，展示插件开发的基本结构与 SDK 用法 |
| `bilibili` | B站直播间链接解析播放 |
| `汕大服务号` | 集成汕大服务号相关功能 |
| `切换ip` | 静态地址切换，支持配置多组网络地址 |

## 开发

### 项目结构

```
touda_wifi_float/
├── main.py                 # 程序入口
├── pyproject.toml          # 项目配置与依赖声明（uv）
├── compile.bat             # 编译脚本（Nuitka）
├── config/                 # 配置文件目录
├── src/                    # 核心功能模块
│   ├── touda.py            # 校园网/WebVPN 核心逻辑
│   ├── config.py           # 配置文件处理
│   ├── plugin_manager.py   # 插件管理器（基于 pluggy）
│   ├── tray.py             # 系统托盘
│   ├── win_float_ball.py   # 悬浮球主窗口
│   └── logging_config.py   # 日志配置
├── ui/                     # 界面模块
│   ├── float_ball.py       # 悬浮球 UI
│   ├── components/         # UI 组件
│   │   ├── waterball.py    # 水球组件
│   │   └── profile.py      # 配置文件组件
│   └── windows/            # 窗口组件
│       ├── drag_window.py      # 拖拽窗口
│       └── settings_window.py  # 设置窗口
├── plugins/                # 插件目录
│   ├── example/            # 示例插件
│   ├── bilibili/           # B站直播解析插件
│   ├── 汕大服务号/          # 汕大服务号插件
│   └── 切换ip/             # 静态地址切换插件
├── res/                    # 资源文件
│   └── ico/                # 图标资源
├── output/                 # 编译输出目录
└── .github/workflows/      # CI/CD 工作流
```

### 技术栈

- **UI 框架**：PySide6 + pyside6-fluent-widgets + pysidesix-frameless-window
- **网络请求**：requests + lxml + beautifulsoup4
- **OTP/加密**：pyotp + mini-racer
- **包管理**：uv + pyproject.toml
- **打包工具**：Nuitka（支持 GitHub Actions 自动构建）

### 编译为可执行文件

#### 使用 GitHub Actions（推荐）

推送 `v*` 格式的 tag 即可自动触发构建工作流，编译产物将作为 Release 附件发布：

```bash
git tag v1.x.x
git push origin v1.x.x
```

#### 本地使用 Nuitka

```bash
# 1）安装依赖（含 nuitka）
uv sync --extra dev
# 2）运行打包脚本
compile.bat
# 或直接使用 uv run：
uv run nuitka --onefile --standalone --mingw64 --output-dir=output --windows-disable-console --windows-icon-from-ico=res/ico/favicon.ico --enable-plugin=pyside6 --include-qt-plugins=sensible,styles --include-data-dir=res/ico=res/ico --follow-imports main.py
```

说明：

- 脚本默认使用 `--onefile --standalone --mingw64` 打包，并启用 PySide6 插件
- 会将 `res/ico/*.ico` 资源打包；插件目录 `plugins/` 也会被包含
- UPX 可选，如需启用，请确保本机已安装并在脚本中配置路径或加入 PATH
- Nuitka 可能需要编译器（MSVC 或 MinGW-w64），按提示安装或让 Nuitka 自动下载

### 依赖包

核心依赖（详见 `pyproject.toml`）：

- `PySide6`: Qt6 Python 绑定
- `pyside6-fluent-widgets`: Fluent Design UI 组件库
- `pysidesix-frameless-window`: 无边框窗口支持
- `requests`: HTTP 请求
- `pyotp`: OTP 动态口令
- `lxml` + `beautifulsoup4`: HTML 解析
- `mini-racer`: JavaScript 执行（无需安装 Node.js）
- `tomlkit`: TOML 配置文件处理
- `pluggy`: 插件系统钩子
- `pywin32`: Windows API 调用

## 🐛 常见问题

### Q：webvpn的key是什么东西？

A：

1. - 如果没有激活webvpn，需要到汕大服务号中激活
   - 如果已经激活了webvpn，需要到汕大服务号中解绑动态口令
2. 在webvpn上登录注册，当需要数盾扫码时，切换另一种格式，复制下来就是key，随后可以继续使用数盾扫码输入口令激活

### Q: 提示"登录失败，密码错误"

A: 请检查 `account_0.toml` 中的账号密码是否正确，注意密码需要 Base64 编码。

### Q: WebVPN 登录失败

A:

1. 检查 `main.toml` 中 WebVPN 配置是否正确
2. 确认已绑定数盾 OTP，key 是否填写正确
3. 查看日志文件确认错误信息
4. 若频繁尝试失败导致账号被锁，请稍后再试或先通过浏览器手动登录一次

### Q: 悬浮球不显示流量

A:

1. 确认已成功登录校园网
2. 检查网络连接是否正常
3. 查看定时器间隔设置（`timer_interval`）

### Q: 源码无法启动

A:

1. 确认 Python 版本 >= 3.12
2. 重新安装依赖：`uv sync`
3. 检查是否有杀毒软件拦截
4. 若缺少 `pluggy` 导致插件系统报错，请手动安装：`uv add pluggy`


## 🤝贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 👥 作者

- [@Tiosa205g](https://github.com/Tiosa205g)

## ⚠️ 免责声明

本工具仅供学习交流使用，请遵守学校网络使用规定。使用本工具产生的任何问题由使用者自行承担。

## 💖 致谢

- [PySide6](https://www.qt.io/qt-for-python)
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- [uv](https://docs.astral.sh/uv/)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ for STU

</div>
