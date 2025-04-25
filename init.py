# TODO: 初始化配置，以便用户填写配置文件
from src import CfgParse
import os
import shutil
def main():
    welcome = '''
    1. 初始化配置文件 2. 修改WiFi账户信息
    3. 添加账户      3. 删除账户
    4. 修改webvpn账户 5. 修改链接
    6. 添加链接      7. 删除链接
    0. 退出
    请输入你的操作(数字)：'''
    
    p = input(welcome)
    if p == '1':
        newFile = ['main', 'account_0', 'links']
        question = ['webvpn账户名','webvpn密码','webvpn密钥','wifi账户名','wifi密码']
        ans = [x for x in map(lambda x: input('请输入{}：'.format(x)), question)]
        # for i in ans:
        #     print('你输入的是{}'.format(i))

        # 清空config文件夹并创建基本配置文件
        if os.path.exists('config'):
            shutil.rmtree('config')
        os.mkdir('config')
        list(map(lambda x: open('config/{}.toml'.format(x),'w'), newFile)) #创建文件

        cfg = [x for x in map(lambda x:CfgParse('config/{}.toml'.format(x)),newFile)]
        cfg[0].write('main','current_account','0')
        cfg[0].write('webvpn','name',ans[0])
        cfg[0].write('webvpn','password',ans[1])
        cfg[0].write('webvpn','key',ans[2])
        cfg[1].write('setting','name',ans[3])
        cfg[1].write('setting','password',ans[4])

        # 写入默认链接
        cfg[2].write('汕大','汕大官网','https://www.stu.edu.cn/')
        cfg[2].write('汕大','教务系统','https://jw.stu.edu.cn/')
        cfg[2].write('汕大','mystu','https://my.stu.edu.cn/')




if __name__ == '__main__':
    main()