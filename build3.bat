cd backend
set python=C:\Python312\python.exe
%python% -m nuitka ^
    --standalone ^
    --windows-console-mode=force ^
    --output-dir=build ^
    --include-module=xuri_rpc_websocket ^
    --include-module=pythonnet ^
    --nofollow-import-to=PyQt5,PyQt6,PySide2,PySide6 ^
    --include-module=clr_loader ^
    --include-module=clr_loader.ffi ^
    --include-module=clr_loader.ffi.hostfxr ^
    --include-module=clr_loader.ffi.netfx ^
    --include-module=clr_loader.util ^
    --include-module=clr_loader.util.find ^
    --include-module=webview.platforms.edgechromium ^
    --disable-plugin=pywebview ^
    --output-dir=..\release ^
main.py
@REM --onefile ^
::什么他妈的叫包名和模块名不是一个东西?