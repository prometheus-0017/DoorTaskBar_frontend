import os
import sys
import time
import ctypes
import ctypes.wintypes
import threading

import webview
import win32api
import win32con
import win32gui

import pywintypes
import traceback


from conf import conf

# ---- win32 常量（用 ctypes 直接调用，避免 pywin32 的同步 SendMessage 不释放 GIL）----
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080  # 不在任务栏 / Alt-Tab 中显示
_WS_EX_TOPMOST = 0x00000008
_WS_EX_APPWINDOW = 0x00040000  # 强制显示任务栏按钮（需清除，否则 TOOLWINDOW 也压不住）
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020
_SMTO_ABORTIFHUNG = 0x0002
_WM_NULL = 0x0000
_SW_HIDE = 0
_SW_SHOWNA = 8  # 显示但不激活（不抢焦点）

# 展开态宽度 / 收起态尺寸（保持与旧版一致）
width = 350
COLLAPSED_W = 2
COLLAPSED_H = 50
TITLE = 'taskbar-sidebar'
URL = 'http://localhost:15000'

window = None


def getWindow():
    global window
    assert window is not None
    return window


class _Signal:
    """轻量信号对象，兼容旧代码里的 xxxSignal.emit() 调用方式。

    旧实现依赖 PySide6.Signal 把调用切回 Qt UI 线程；pywebview 的
    resize/move 本身是线程安全的（内部会 marshal 到 GUI 线程），
    因此这里直接同步调用目标函数即可。
    """

    def __init__(self, fn):
        self._fn = fn

    def emit(self, *args):
        try:
            self._fn(*args)
        except Exception:
            traceback.print_exc()


class CustomWindow:
    def __init__(self):
        self.webWindow = None
        self._expanded = True  # 初始按旧逻辑处于展开态
        self._entered_once = False  # 鼠标首次进入前不自动收起（对齐旧 leaveEvent 语义）
        self._closed = False

        # 兼容旧的信号接口（rpc_content.py / http_server.py 在用）
        self.exitSignal = _Signal(self.exit)
        self.expandSignal = _Signal(self.expand)
        self.collapseSignal = _Signal(lambda: self.collapse(True))

    # ---- 屏幕尺寸 ----
    def fullHeight(self):
        return win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

    # ---- 生命周期 ----
    def exit(self):
        # 从任意线程可靠退出整个进程
        os._exit(0)

    def expand(self):
        if self.webWindow is None:
            return
        self._expanded = True
        self.webWindow.resize(width, self.fullHeight())
        self.webWindow.move(0, 0)

    def collapse(self, force=True):
        if self.webWindow is None:
            return
        # force=False 时，若鼠标仍在窗口范围内则不收起（对齐旧 collapse 逻辑）
        if not force and self._cursor_inside():
            return
        self._expanded = False
        self.webWindow.resize(COLLAPSED_W, COLLAPSED_H)
        self.webWindow.move(0, 0)

    # ---- 鼠标位置判定 ----
    def _current_rect(self):
        left, top = 0, 0
        if self._expanded:
            w, h = width, self.fullHeight()
        else:
            w, h = COLLAPSED_W, COLLAPSED_H
        return left, top, left + w, top + h

    def _cursor_inside(self):
        x, y = win32api.GetCursorPos()
        x1, y1, x2, y2 = self._current_rect()
        return x1 <= x <= x2 and y1 <= y <= y2

    @staticmethod
    def _is_dragging():
        """检测鼠标左键是否处于按下状态（拖拽中）。
        GetKeyState 返回值的高位为 1 表示按键被按下。
        """
        return win32api.GetKeyState(win32con.VK_LBUTTON) & 0x8000 != 0

    # ---- 悬停轮询：替代旧的 enterEvent / leaveEvent ----
    def _poll_loop(self):
        while not self._closed:
            time.sleep(0.1)
            try:
                dragging = self._is_dragging()
                inside = self._cursor_inside()
                if inside:
                    self._entered_once = True
                    if not self._expanded:
                        # 鼠标进入触发区（也覆盖拖拽文件经过侧边条的场景）→ 展开
                        self.expand()
                elif self._expanded and self._entered_once:
                    # 仅在鼠标至少进入过一次后才自动收起，避免启动即消失
                    if conf['pin']:
                        continue
                    # 鼠标左键按下（拖拽状态）时不收起，防止拖拽文件时界面消失
                    if dragging:
                        continue
                    self.collapse(False)
            except Exception as e:
                if isinstance(e, pywintypes.error):
                    if(e.args[0:2]==(5,'GetCursorPos')):
                        # GetCursorPos 错误 permission denied
                        # 当鼠标移动到特权窗口会触发,所以不见得是需要处理的错误
                        pass
                    else:
                        traceback.print_exc()

    # ---- 窗口原生样式：无边框已由 pywebview 处理，这里补工具窗口/置顶 ----
    def _apply_native_style(self):
        # 关键：全程用 ctypes 调 user32（ctypes 调用外部函数时会释放 GIL），
        # 绝不能用 pywin32 的 win32gui.SetWindowLong —— 它做同步跨线程 SendMessage
        # 且不释放 GIL，会与 UI 线程 on_shown 里的 webview.Focus() 互锁（进程未响应）。
        user32 = ctypes.windll.user32
        # 显式声明原型：64 位下 HWND 是 64 位句柄，ctypes 默认按 c_int 传参会截断句柄。
        wt = ctypes.wintypes
        user32.SendMessageTimeoutW.argtypes = [
            wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        user32.SendMessageTimeoutW.restype = wt.LPARAM
        user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wt.LONG
        user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
        user32.SetWindowLongW.restype = wt.LONG
        user32.SetWindowPos.argtypes = [
            wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, wt.UINT,
        ]
        user32.SetWindowPos.restype = wt.BOOL
        user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wt.BOOL
        hwnd = 0
        for _ in range(100):
            hwnd = win32gui.FindWindow(None, TITLE)
            if hwnd:
                break
            time.sleep(0.1)
        if not hwnd:
            return
        # 等 UI 线程真正回到消息循环（可响应）后再改样式，避免与初始化/Focus() 抢占。
        result = ctypes.c_size_t(0)
        for _ in range(100):
            ok = user32.SendMessageTimeoutW(
                hwnd, _WM_NULL, 0, 0, _SMTO_ABORTIFHUNG, 300, ctypes.byref(result)
            )
            if ok:
                break
            time.sleep(0.05)
        ex = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        ex |= _WS_EX_TOOLWINDOW
        ex |= _WS_EX_TOPMOST
        ex &= ~_WS_EX_APPWINDOW  # 清除 APPWINDOW，否则任务栏按钮无法去掉
        user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex)
        user32.SetWindowPos(
            hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_FRAMECHANGED | _SWP_NOACTIVATE,
        )
        # Windows 只在窗口“显示时”决定是否入任务栏；pywebview 先显示了窗口（此时
        # 还没有 WS_EX_TOOLWINDOW），所以任务栏按钮已经生成。加上样式后需要隐藏
        # 再重新显示，让系统重新评估——这样才能真正去掉那个任务栏按钮。
        user32.ShowWindow(hwnd, _SW_HIDE)
        user32.ShowWindow(hwnd, _SW_SHOWNA)

    def _on_shown(self):
        # 'shown' 在窗口显示后触发，但此回调运行在 pywebview 事件线程上，
        # 而 UI 线程紧接着还要执行 webview.Focus()。这里必须用 ctypes 版
        # _apply_native_style（释放 GIL + 先探测窗口可响应），否则会死锁。
        self._apply_native_style()
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def create(self):
        self.webWindow = webview.create_window(
            TITLE,
            url=URL,
            frameless=True,
            on_top=True,
            resizable=False,
            width=width,
            height=self.fullHeight(),
            x=0,
            y=0,
            min_size=(1, 1),
            easy_drag=False,
        )
        assert self.webWindow!=None
        self.webWindow.events.shown += self._on_shown
        return self.webWindow
import pythonnet

def startView():
    import signal

    global window

    def handler(sig, frame):
        import rpc_content
        rpc_content.exit(None)

    try:
        signal.signal(signal.SIGINT, handler)
    except Exception:
        pass

    window = CustomWindow()
    window.create()
    # 使用 WebView2（Edge Chromium）内核，避免打包 Qt WebEngine 的整套 Chromium
    webview.start(gui='edgechromium', private_mode=False)


if __name__ == '__main__':
    startView()
