import conf
def showTaskbar():
    import requests
    try:
        res=requests.post(f'http://127.0.0.1:{conf.get('httpPort')}/expand')

        if(res.status_code==200):
            print('已发送展开请求')
            return 

    except Exception:
        pass

    print('展开请求发送失败')
def registerKeyboardListener():
    import keyboard
    keyboard.add_hotkey('ctrl+alt+comma', showTaskbar)
def unregisterKeyboardListener():
    import keyboard
    keyboard.remove_hotkey('ctrl+alt+comma')
def singleMain():
    try:
        registerKeyboardListener()
        input()
    except Exception:
        import traceback
        traceback.print_exc()
        while(True):
            import time
            time.sleep(2)

        
from pathlib import Path
import sys
from util import confirm,is_admin
def tryStartKeyboardListener():
    import ctypes
    if(is_admin()):
        registerKeyboardListener()
    else:
        wantAdmin=confirm('当前非管理员权限,是否运行一个管理员进程以支持全局监听弹出任务栏热键?否,则仅不启用热键功能')
        if(wantAdmin):
            script_path = Path('show_taskbar.py').absolute().__str__()
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, script_path, None, 1
                )
            except Exception as e:
                print(f"提权失败: {e}")
        else:
            print('不开启全局热键')

if(__name__ == '__main__'):
    singleMain()
