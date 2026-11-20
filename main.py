import sys
if('.' not in sys.path):
    sys.path.append('.')
import os

# ---- Nuitka 打包后 pythonnet / clr_loader 的 DLL 路径修复 ----
# pythonnet 用 Path(__file__) 定位 Python.Runtime.dll，
# clr_loader 用 Path(__file__) 定位 ClrLoader.dll。
# Nuitka standalone 打包后 __file__ 可能无法正确解析，这里手动修正。
if getattr(sys, 'frozen', False) or '__compiled__' in dir():
    _base = os.path.dirname(os.path.abspath(sys.executable))
    # 修正 pythonnet.__file__
    import pythonnet
    _pn_init = os.path.join(_base, 'pythonnet', '__init__.py')
    if not os.path.exists(_pn_init):
        os.makedirs(os.path.join(_base, 'pythonnet'), exist_ok=True)
        with open(_pn_init, 'w') as _f:
            _f.write('')
    pythonnet.__file__ = _pn_init
    # 修正 clr_loader.ffi.__file__
    import clr_loader.ffi
    _cl_init = os.path.join(_base, 'clr_loader', 'ffi', '__init__.py')
    if not os.path.exists(_cl_init):
        os.makedirs(os.path.join(_base, 'clr_loader', 'ffi'), exist_ok=True)
        with open(_cl_init, 'w') as _f:
            _f.write('')
    clr_loader.ffi.__file__ = _cl_init
    # 预先加载 pythonnet，后续 import clr 会直接跳过
    pythonnet.load()
# ---- END pythonnet 路径修复 ----

dllPath=os.environ.get('dllPath')
print(dllPath)
if(dllPath):
    print('adding',dllPath)
    os.add_dll_directory(dllPath)
from util import detach,is_port_in_use,messageBox
# os.add_dll_directory(r'C:\Users\lzy\Desktop\taskbar\python-3.12.7-embed-amd64\Lib\site-packages\pywin32_system32')

import conf
import sys



from http_server import startHttpServer
from ui import startView
from websocket_server import startWebSocket
from show_taskbar import tryStartKeyboardListener
from util import setEnv

# setEnv('taskbar_http_port',conf.get('httpPort'))

detach(startHttpServer)
detach(startWebSocket)
def env():
    import lock
    setEnv('taskbar_http_port',conf.get('httpPort'))
    while(is_port_in_use(conf.get('httpPort'))==False):
        import time
        time.sleep(0.1)
    lock.setOK(lock.FLAG_HTTP_START)
detach(env)
import lock
lock.waitForStart()
# detach(tryStartKeyboardListener)
startView()