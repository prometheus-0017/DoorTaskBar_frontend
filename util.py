from threading import Thread
import ctypes
def detach(func):
    t=Thread(target=func,daemon=True)
    t.start()
    return t

import socket

def is_port_in_use(port, host='0.0.0.0'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False  # 成功绑定，说明端口未被占用
        except socket.error|OSError as e:
            return True   # 绑定失败，端口被占用
import win32api
import win32con

def messageBox(text):
    win32api.MessageBox(0, text, '提示', win32con.MB_OK | win32con.MB_ICONINFORMATION)

def confirm(text='你确定要继续吗？'):    

    response = win32api.MessageBox(0, text, '确认', win32con.MB_YESNO | win32con.MB_ICONQUESTION)

    if response == win32con.IDYES:
        return True
    else:
        return False

import subprocess
def setEnv(key,value):
    if(type(value)==int):
        value=str(value)
    result = subprocess.run(['setx', key, value], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"环境变量已设置{key}={value}")
    else:
        print("环境变量设置失败:", result.stderr)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False