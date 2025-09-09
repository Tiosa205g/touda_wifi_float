from src import CfgParse
import os
import sys
import shutil
import base64
import pyperclip
def main():
    welcome = '''
    1. 初始化配置文件 2. 修改WiFi账户信息
    3. 添加账户      4. 删除账户
    5. 修改webvpn账户 6. 修改链接
    7. 添加链接      8. 删除链接
    9. 导入导出链接
    0. 退出
    请输入你的操作(数字)：'''
    p = input(welcome)
    if p == '0':
        sys.exit()
    elif p == '1':
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
        cfg[0].write('webvpn','password',base64.b64encode(ans[1].encode('utf-8')).decode('utf-8'))
        cfg[0].write('webvpn','key',ans[2])
        cfg[1].write('setting','name',ans[3])
        cfg[1].write('setting','password',base64.b64encode(ans[4].encode('utf-8')).decode('utf-8'))

        # 写入默认链接
        cfg[2].write('汕大','汕大官网','https://www.stu.edu.cn/')
        cfg[2].write('汕大','教务系统','https://jw.stu.edu.cn/')
        cfg[2].write('汕大','mystu','https://my.stu.edu.cn/')
        print('完成')
    elif p == '2':
        acc = input('需要修改第几个账户？（从0开始）:')
        name = input('请输入账户名：')
        password = base64.b64encode(input('密码').encode('utf-8'))
        if not acc.isdigit():
            print('输入错误')
            return
        cfg = CfgParse('config/account_{}.toml'.format(acc))
        cfg.write('setting','name',name)
        cfg.write('setting','password',password)
        print('完成')
    elif p == '3':
        name = input('请输入账户名:')
        password = base64.b64encode(input('请输入密码:').encode('utf-8')).decode('utf-8')
        # 遍历 config目录下account_{}.toml文件的数量
        acc = []
        i = 0
        for file in os.listdir('config'):
            if 'account_' in file and '.toml' in file:
                acc.append("config/"+file)
        while True:
            t = len(acc)+i-1
            if os.path.exists("config/account_{}.toml".format(t)):
                i+=1
                continue
            open('config/account_{}.toml'.format(t),'w')
            cfg = CfgParse('config/account_{}.toml'.format(t))
            cfg.write('setting','name',name)
            cfg.write('setting','password',password)
            print('完成')
            break
    elif p == '4':
        acc = input('需要删除第几个账户?（从0开始）:')
        # current相同则改成 0
        if not acc.isdigit():
            print('请输入数字')
            return
        if acc == '0':
            print('0号账户不能删除只能修改')
            return
        os.remove('config/account_{}.toml'.format(acc))
        mainCfg = CfgParse('config/main.toml')
        if mainCfg.get("main","current_account") == acc:
            mainCfg.write('main','current_account','0')
        print('完成')
    elif p == '5':
        cfg = CfgParse('config/main.toml')
        name = input('请输入账户名:')
        password = base64.b64encode(input('请输入密码:').encode('utf-8')).decode('utf-8')
        key = input('请输入密钥:')
        cfg.write('webvpn','name',name)
        cfg.write('webvpn','password',password)
        cfg.write('webvpn','key',key)
        print('完成')
    elif p == '6':
        link_type = input('请输入链接类型:')
        cfg = CfgParse('config/links.toml')
        link_all = cfg.get_all()
        if link_type not in link_all:
            print('没有这个链接类型')
            return

        link_name = input('请输入链接名:')

        if link_name not in link_all[link_type]:
            print('没有这个链接名')
            return

        link = link_all[link_type][link_name]
        fix_type = none_to_other(input('请输入修改后链接类型（保留请留空）：'),link_type)
        fix_name = none_to_other(input('请输入修改后链接名（保留请留空）：'),link_name)
        fix_link = none_to_other(input('请输入修改后链接（保留请留空）：'),link)
        del link_all[link_type][link_name]
        if len(link_all[link_type]) == 0:
            del link_all[link_type]
        cfg.set_all(link_all)
        cfg.write(fix_type,fix_name,fix_link)
        print('完成')
    elif p == '7':
        cfg = CfgParse('config/links.toml')
        link_type = input('请输入链接类型:')
        link_name = input('请输入链接名:')
        link = input('请输入链接:')
        cfg.write(link_type,link_name,link)
        print('完成')
    elif p == '8':
        cfg = CfgParse('config/links.toml')
        link_all = cfg.get_all()
        link_type = input('请输入链接类型:')
        if link_type not in link_all:
            print('没有这个链接类型')
            return
        link_name = input('请输入链接名:')
        if link_name not in link_all[link_type]:
            print('没有这个链接名')
            return

        del link_all[link_type][link_name]
        if len(link_all[link_type]) == 0:
            del link_all[link_type]
        cfg.set_all(link_all)
        print('完成')
    elif p == '9':
        choice = input('1. 导出链接 2. 导入链接 0. 返回\n请输入操作:')
        if choice == '1':
            link_type = input('请输入链接类型:')
            links = CfgParse('config/links.toml').get_all()
            if link_type not in links:
                print('没有这个链接类型')
                return
            pyperclip.copy(base64.b64encode(str(links[link_type]).encode('utf-8')).decode('utf-8'))
            print('已复制到剪切板')
        elif choice == '2':
            put = eval(base64.b64decode(input("请输入软件所导出的链接:").encode('utf-8')).decode('utf-8'))
            links = CfgParse('config/links.toml').get_all()
            try:
                if type(put) != dict:
                    print('格式错误')
                    return
                link_type = input('导入后的链接类型(若已存在会在以前基础上覆盖):')
                links.update({link_type:put})
                CfgParse('config/links.toml').set_all(links)
                print('完成')
            except Exception as e:
                print('格式错误',e)
        elif choice == '0':
            return

def none_to_other(may,other):
    if may == '':
        return other
    return may
if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print('发生错误：',e)
