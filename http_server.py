from flask import Flask,abort,send_file,request
import conf
import websocket_server
from window_proxy import iconManager
from pathlib import Path
from threading import Thread
from io import BytesIO

app=Flask(__name__)


@app.before_request
def _check_remote():
    if conf.get('allowRemote'):
        return None
    _LOCAL_HOSTS={'127.0.0.1','localhost','::1'}
    remote=request.remote_addr
    if remote and remote not in _LOCAL_HOSTS:
        abort(403)
    return None
# Path('icons').mkdir(exist_ok=True)
from typing import Optional
@app.route('/icons/<path:path>',methods=['GET'])
def send_assets(path):
    # 从iconManager的缓存中获取图片
    hash=path
    img:Optional[bytes]=iconManager.getIconByHash(hash);
    if(img==None):
        abort(404)
    else:
        return send_file(BytesIO(img),'image/png')

        
@app.route('/')
def index():
    return send_file('dist/index.html')

@app.route('/expand',methods=['POST'])
def expand():
    from ui import getWindow
    getWindow().expandSignal.emit()
    return ''

@app.route('/firm',methods=['POST'])
def firm():
    import rpc_content
    result = rpc_content.dumpSave()
    return {'dumped': result}
    

@app.route('/<path:path>')
def static2(path):
    return send_file(f'dist/{path}')
# @app.route('/dist/<path:path>')
# def send_dist(path):
#     return send_file('dist/'+path)
import lock
import sys
from util import is_port_in_use,messageBox,setEnv
def startHttpServer():

    if(is_port_in_use(conf.get('httpPort'))):
        messageBox(f'{conf.get('httpPort')}端口被占用')
        sys.exit(1)

    lock.setOK(lock.FLAG_HTTP)
    lock.waitForCheck()
    print('http continue')

    app.run(host='0.0.0.0',port=conf.get('httpPort'),debug=False)

if __name__ == '__main__':
    startHttpServer()
