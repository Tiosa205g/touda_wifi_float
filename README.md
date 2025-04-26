# Touda_WiFi 悬浮窗版
## 使用的特殊库:
1. pyside6
2. tomlkit
## 日志:
- 25.3.17:建仓
- 鸽子
- 25.4.26:完成基本功能

## 文件结构
### links.toml 结构
- type:链接类型(str)
  - name:链接名称(str)
    - link:链接地址(str)
### account_[NUM].toml 结构
- name:用户名(str)
- password:密码(str/base64编码)
