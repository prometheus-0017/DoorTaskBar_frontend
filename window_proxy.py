import win32gui
import win32api
import win32con
import win32ui
from io import BytesIO
import win32process
from typing import Optional
from PIL import Image
import hashlib

from threading import Lock
foregroundLock = Lock()

def set_foreground_window(hwnd):
    # 获取当前线程ID
    current_thread_id = win32api.GetCurrentThreadId()
    # 获取目标窗口的线程ID和进程ID
    thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
    
    # 将当前线程与目标窗口线程关联
    win32process.AttachThreadInput(current_thread_id, thread_id, True)
    
    # 恢复窗口
    # win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    
    # 设置为前台窗口
    win32gui.SetForegroundWindow(hwnd)
    
    # 分离线程输入
    win32process.AttachThreadInput(current_thread_id, thread_id, False)
def setTop(hwnd):
    with foregroundLock:
        #对于最小化窗口需要特殊处理
        if(win32gui.IsIconic(hwnd)):
            win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
        try:
            succ=win32gui.SetForegroundWindow(hwnd)
            print('foreground success')
            return
        except:
            import traceback
            traceback.print_exc()
        try:
            set_foreground_window(hwnd)
            # win32gui.SetFocus(hwnd)
            # win32gui.SetForegroundWindow(hwnd)
            print('focus foreground success')
            return 
        except:
            import traceback
            traceback.print_exc()

        # try:
        #     resultWindow=win32gui.ShowWindow(hwnd,win32con.SW_SHOW)
        #     if(resultWindow==0):
        #         raise Exception('fail')
        #     print('showWindow success')
        #     return
        # except:
        #     import traceback
        #     traceback.print_exc()
        try:
            succ=win32gui.BringWindowToTop(hwnd)
            print('bringWindowToTop success')
        except:
            import traceback
            traceback.print_exc()


    


windowIds:set=set()
def refresh():
    newWindows=WindowProxy.getTopWindow().listChildren()
    newWindowsDict:dict={window.hwnd:window for window in newWindows}
    newIds:set=set(newWindowsDict.keys())
    new=newIds-windowIds
    deleted=windowIds-newIds
    for windowId in new:
        window:WindowProxy=newWindowsDict[windowId]
        window.saveIcon()
    for windowId in deleted:
        window:WindowProxy=newWindowsDict[windowId]
        # window.deleteIcon()
        
def isWindow(hwnd):
    if not win32gui.IsWindowVisible(hwnd):
        return False
    class_name = win32gui.GetClassName(hwnd)
    title = win32gui.GetWindowText(hwnd)

    if class_name == "tooltips_class32":
        return False
    # 对话框类窗口默认丢弃，但带 WS_EX_APPWINDOW 的是系统认定要进任务栏的窗口(如 TortoiseGit 各对话框)
    if class_name == "#32770":
        if not win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_APPWINDOW:
            return False
    
    # 确保是顶级窗口（非子窗口）
    root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
    if root_hwnd != hwnd:
        return False
    
    if not title:
        return False
    return True
class IconManager:
    def __init__(self):
        self.hash2data = {}  # hash -> icon data mapping
        self.hwnd2hash = {}  # hwnd -> hash mapping
        self.hashCount = {}  # reference count for each hash
    
    def saveIcon(self, window:'WindowProxy') -> str:
        hwnd = window.hwnd
        
        # Check if we already have a hash for this window
        if hwnd in self.hwnd2hash:
            return self.hwnd2hash[hwnd]
        
        hIconHandle = win32gui.GetClassLong(window.hwnd, win32con.GCL_HICON)
        if hIconHandle == 0:
            path = window.getProcessPath()
            try:
                hIconHandle = win32gui.ExtractIcon(None, path, 0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(path)
        
        if hIconHandle == 0:
            return None
        
        # Create a device context (DC)
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()

        # Get icon info
        icon_info = win32gui.GetIconInfo(hIconHandle)
        # icon_size = icon_info[3]  # This was incorrectly getting size, should be width and height from bitmap
        hIcon = hIconHandle
        icon_size = win32gui.GetIconInfo(hIcon)
        
        # Get the bitmap information for the icon
        bitmap = win32gui.GetObject(icon_info[3])
        w = bitmap.bmWidth
        h = bitmap.bmHeight
        
        # Create a bitmap compatible with the DC
        hbmp.CreateCompatibleBitmap(hdc, w, h)
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)

        # Draw the icon
        hdc.DrawIcon((0, 0), hIcon)

        # Convert bitmap to PIL image
        bmpstr = hbmp.GetBitmapBits(True)
        image = Image.frombuffer('RGB', (w, h), bmpstr, 'raw', 'BGRX', 0, 1)
        memBuffer = BytesIO()
        image.save(memBuffer, "PNG")

        # Generate a hash of the icon data
        icon_data = memBuffer.getvalue()
        icon_hash = hashlib.md5(icon_data).hexdigest()
        
        # Store the icon data with its hash
        if icon_hash not in self.hash2data:
            self.hash2data[icon_hash] = icon_data
            self.hashCount[icon_hash] = 0
            
        # Map the window to the hash
        self.hwnd2hash[hwnd] = icon_hash
        self.hashCount[icon_hash] += 1

        # Cleanup
        try:
            win32gui.ReleaseDC(0, hdc.GetSafeHdc())
            win32gui.DestroyIcon(hIcon)
        except:
            import traceback
            traceback.print_exc()
            
        return icon_hash

    def getIconByHash(self, icon_hash: str)->Optional[bytes]:
        """Retrieve icon data by its hash"""
        if icon_hash not in self.hash2data:
            return None
        self.hashCount[icon_hash] += 1
        return self.hash2data.get(icon_hash)
    
    def getIconByHWND(self, hwnd):
        """Get icon data by window handle"""
        icon_hash = self.hwnd2hash.get(hwnd)
        if icon_hash is None:
            return None
        return self.getIconByHash(icon_hash)
        
    def removeIcon(self, hwnd):
        """Remove icon mapping for a window"""
        if hwnd in self.hwnd2hash:
            icon_hash = self.hwnd2hash[hwnd]
            del self.hwnd2hash[hwnd]
            
            # Decrease reference count
            self.hashCount[icon_hash] -= 1
            if self.hashCount[icon_hash] <= 0:
                # Remove the icon data if no references remain
                del self.hash2data[icon_hash]
                del self.hashCount[icon_hash]
iconManager=IconManager()

import psutil
class MyException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
    pass
def get_process_cwd(pid):
    try:
        proc = psutil.Process(pid)
        # 在 Windows 上，cwd() 返回进程当前工作目录
        return proc.cwd()
    except psutil.NoSuchProcess:
        raise MyException("进程不存在")
    except psutil.AccessDenied:
        raise MyException("权限不足")
    except Exception as e:
        raise e

class WindowProxy:
    def getId(self):
        return self.hwnd
    def _iconPath(self):
        return f'icons/{iconManager.hwnd2hash.get(self.hwnd,"0000")}'
    def getIconPath(self):
        return self._iconPath()
    def __init__(self,previous:'WindowProxy',hwnd):
        self.hwnd = hwnd
        self.previous = previous
        self.name=''
        pass
    def saveName(self):
        self.name=self.getTitle()
    def getPrevName(self):
        return self.name
    def saveIcon(self) -> str:
        return iconManager.saveIcon(self)
        # hIconHandle= win32gui.GetClassLong(self.hwnd,win32con.GCL_HICON)
        # if(hIconHandle==0):
        #     return None
        # hIcon=win32gui.GetIconInfo(hIconHandle)
        # bitmap=win32gui.GetObject(hIcon[3])
        # save_icon_to_bitmap(hIconHandle,self._iconPath())
        # return bitmap
        
        pass
    def deleteIcon(self):
        pass
    def getProcess(self):
        res= win32process.GetWindowThreadProcessId(self.hwnd)
        return res[1]
    def getTitle(self)->str:
        return win32gui.GetWindowText(self.hwnd)
        pass
    def toTop(self):
        setTop(self.hwnd)
    def getProcessFileName(self):
        res=self.getProcessPath();
        if(res==None):
            return ''
        idx=res.rfind("\\")
        if(idx!=-1):
            res=res[idx+1:]
        return res
        
    def getProcessPath(self):
        pid = self.getProcess()
        try:
            h_process = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid
            )
            if not h_process:
                raise Exception("无法打开进程，权限不足或进程已退出")
        
            res=win32process.GetModuleFileNameEx(h_process,None)
            
            return res
        except:
            import traceback
            # print('fail:',pid)
            # traceback.print_exc()
            return 'none'

    def getPwd(self)->str:
        pid=self.getProcess()
        try:
            return get_process_cwd(pid)
        except MyException as e:
            print(self.getTitle(),e.args[0])
        except Exception as e:
            #pid must be a positive integer
            if(len(e.args)>0 and 'pid must be a positive integer' in e.args[0]):
                print('strange pid')
            else:
                import traceback
                traceback.print_exc()
            return 'none'

    def listChildren(self)->list['WindowProxy']:
        #win32gui.GetWindow(self.hwnd,win32gui.GW_CHILD) 不建议

        def callback(hwnd,param):
            param.append(WindowProxy(self,hwnd))
            return True
        vl:list[WindowProxy]=[]
        win32gui.EnumChildWindows(self.hwnd,callback,vl)
        return [x for x in vl if isWindow(x.hwnd)]
    def getClass(self):
        return win32gui.GetClassName(self.hwnd)
    @classmethod
    def getTopWindow(cls)->'WindowProxy':
        return WindowProxy(None,win32gui.GetDesktopWindow())
        # return WindowProxy(None,win32gui.GetForegroundWindow())
# for p in WindowProxy.getTopWindow().listChildren():
#     txt=p.getTitle()
#     # icon=p.getIcon()
#     # if(icon==None):
#     #     continue
#     if(txt.strip()==''):
#         continue
#     if(p.getClass().lower()=='notepad'):
#         print(p.getClass())
#         p.toTop()


# p.saveIcon() 