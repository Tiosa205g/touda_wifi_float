# Touda_WiFi 悬浮窗版
## 使用的特殊库:
    1.pyside6
    2.tomlkit
## 日志:
    - 25.3.17:建仓

## TODO: （使用fluent-widget）
    1.悬浮窗流量显示
    2.右键菜单(链接)
        - 链接外再拓展子菜单直接访问以及webvpn访问
    3.Tray托盘以及上下文菜单控制显示隐藏

## 文件结构
### links.toml 结构
- (json数组)
    - name:类名(str)
        - (json数组)
            - name:显示名称(str)
            - link:链接(str)
### account_[NUM].toml 结构
- name:用户名(str)
- password:密码(str/AES编码)
