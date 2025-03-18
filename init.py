# TODO: 初始化配置，以便用户填写配置文件
import toml
def main():
    welcome = '''
    1. 初始化配置文件 2. 修改WiFi账户信息
    3. 添加账户      3. 删除账户
    4. 修改webvpn账户 5. 添加webvpn账户
    6. 删除webvpn账户 7. 修改链接
    8. 添加链接      9. 删除链接
    0. 退出
    请输入你的操作(数字)：'''
    
    p = input(welcome)

if __name__ == '__main__':
    main()