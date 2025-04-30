# Touda_WiFi 悬浮窗版

## 使用的第三方库:
1. pyside6
2. tomlkit
3. requests
4. pyperclip
5. lxml
6. beautifulsoup4
7. PySide6-Fluent-Widgets
8. pyotp
9. nuitka(打包工具-可选)
10. auto-py-to-exe(打包工具-可选)
## 日志:
- 25.3.17:建仓
- 鸽子
- 25.4.26:完成基本功能

## 文件结构
## config
- ### links.toml 结构
  - type:链接类型(str)
    - name:链接名称(str)
      - link:链接地址(str)
- ### account_[NUM].toml 结构
  - name:用户名(str)
  - password:密码(str/base64编码)
- ### main.toml 结构
  - main
    - current_account:当前登录账号的索引(int)
  - webvpn
    - name:webvpn用户名(str) 
    - password:webvpn密码(str/base64编码)
    - key:webvpn密钥(str)