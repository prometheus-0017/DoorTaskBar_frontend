import window_proxy
from typing import TypedDict,Union,Literal
from window_proxy import WindowProxy
windowsBefore:dict[int,WindowProxy]={}
version=0


class WindowProxyDTO(TypedDict):
    processId:int
    id:int
    originalName:str
    modifiedName:str
    processName:str
    originalIcon:str
    modifiedIcon:str
    pwd:str
    system:str
class WindowChangeInfo(TypedDict):
    type:Literal['add','change','delete']
    data:WindowProxyDTO

from typing import Callable, Awaitable
callbacklist:dict[str,Callable[[list[WindowChangeInfo]],Awaitable[None]]]={}

import asyncio
from logging import getLogger
logger=getLogger(__name__)
import logging
logging.basicConfig(level=logging.INFO,filename='log.txt')
async def setCallback(context,id,callback):
    # 必须得标记callback的身份,因为无法确认对面是真的走了还是网络暂时断开
    callbacklist[id]=callback
    
def startWindowsDetectLoop():
    async def loop():
        while True:
            try:
                await asyncio.sleep(1);
                await detectChange()
            except Exception as e:
                traceback.print_exc()
    asyncio.ensure_future(loop())

from websockets.exceptions import ConnectionClosedError
async def _notify(infos:list[WindowChangeInfo]):
    for key in callbacklist:
        callback=callbacklist[key]
        try:
            await callback(infos)
        except ConnectionClosedError:
            # callbacklist.remove(callback)
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            del callbacklist[key]
async def echo(context):
    return '1'
async def checkLogin(context,id:str):
    return id in callbacklist

class ChromeProxy:
    async def sync(self)->list[WindowProxyDTO]:
        ...
    async def toTop(self,windowsId:str):
        ...
    async def getHost(self)->str:
        ...
chromeClients:dict[str,ChromeProxy]={}

class ChromeClientState:
    def __init__(self, proxy:'ChromeProxy'):
        self.proxy = proxy
        self.prevWindows: list[WindowProxyDTO] = []
        self.tick: int = 0

chromeClientStates: dict[str, ChromeClientState] = {}

def _chromeWindowsToDTOs(windows: list) -> list[WindowProxyDTO]:
    return [WindowProxyDTO(
        processId=w.get('processId', 0),
        id=w.get('id', 0),
        pwd=w.get('pwd', ''),
        system=w.get('system', 'chrome'),
        originalName=w.get('originalName', ''),
        modifiedName=w.get('modifiedName', ''),
        processName=w.get('processName', ''),
        originalIcon=w.get('originalIcon', ''),
        modifiedIcon=w.get('modifiedIcon', '')
    ) for w in windows]

def _chromeDiff(hostId: str, currentWindows: list[WindowProxyDTO]) -> list[WindowChangeInfo]:
    state = chromeClientStates[hostId]
    prevMap = {w['id']: w for w in state.prevWindows}
    currMap = {w['id']: w for w in currentWindows}
    prevIds = set(prevMap.keys())
    currIds = set(currMap.keys())
    updates: list[WindowChangeInfo] = []
    for wid in currIds - prevIds:
        updates.append(WindowChangeInfo(type='add', data=currMap[wid]))
    for wid in prevIds - currIds:
        updates.append(WindowChangeInfo(type='delete', data=prevMap[wid]))
    for wid in prevIds & currIds:
        pw = prevMap[wid]
        cw = currMap[wid]
        if pw.get('originalName') != cw.get('originalName') or pw.get('modifiedName') != cw.get('modifiedName'):
            updates.append(WindowChangeInfo(type='change', data=cw))
    state.prevWindows = currentWindows
    return updates

import traceback
async def loginChrome(context, chromeProxy):
    hostId = await chromeProxy.getHost()
    chromeClients[hostId] = chromeProxy
    chromeClientStates[hostId] = ChromeClientState(chromeProxy)
    currentWindows = await chromeProxy.sync()
    currentDTOs = _chromeWindowsToDTOs(currentWindows)
    state = chromeClientStates[hostId]
    if state.prevWindows:
        diffs = _chromeDiff(hostId, currentDTOs)
        state.tick += 1
        if diffs:
            asyncio.ensure_future(_notify(diffs))
    else:
        state.prevWindows = currentDTOs
        state.tick = 0
        adds = [WindowChangeInfo(type='add', data=x) for x in currentDTOs]
        if adds:
            asyncio.ensure_future(_notify(adds))

async def sync(context):
    res=[]
    res+= [WindowProxyDTO(
        processId=v.getProcess(),
        id=v.getId(),
        pwd=v.getPwd(),
        system='win',
        originalName=v.getTitle(),
        modifiedName='',
        processName=v.getProcessFileName(),
        originalIcon=v.getIconPath(),
        modifiedIcon=v.getIconPath()
    ) for v in windowsBefore.values()]
    for hostId in chromeClientStates:
        try:
            res += chromeClientStates[hostId].prevWindows
        except Exception as e:
            traceback.print_exc()
    return res
async def detectChange():
    global windowsBefore

    windowList:list[WindowProxy]=WindowProxy.getTopWindow().listChildren()
    windowsNow={item.hwnd:item for item in windowList}
    infoUpdates:list[WindowChangeInfo]=[]
    old=[windowsBefore[k] for k in windowsBefore.keys()-windowsNow.keys()]
    new=[windowsNow[k] for k in windowsNow.keys()-windowsBefore.keys()]
    common=[windowsNow[k] for k in windowsNow.keys()&windowsBefore.keys() if(windowsBefore[k].getPrevName()!=windowsNow[k].getTitle())]
    for v in old:
        logger.info(f'delete {v.getId()} {v.getTitle()}')
    for v in new:
        logger.info(f'add {v.getId()} {v.getTitle()}')
        v.saveIcon()
    for v in new:
        v.saveIcon()
    for v in common:
        v.saveName()
    infoUpdates.extend([WindowChangeInfo(
        type='delete',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        ) )for v in old])
    infoUpdates.extend([WindowChangeInfo(
        type='add',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        ) )for v in new])
    infoUpdates.extend([WindowChangeInfo(
        type='change',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),#with lock when sync
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        )
    ) for v in common])

    windowsBefore=windowsNow
    # await notify(infoUpdates)
    if(infoUpdates.__len__()!=0):
        asyncio.ensure_future(_notify(infoUpdates))
async def notify(context, payload):
    # chrome only?bad name
    hostId=payload.hostId
    state = chromeClientStates[hostId]
    # if not isinstance(payload, dict) or 'infos' not in payload or 'tick' not in payload:
    #     print('unknown notifyData', payload)
    #     return
    infos = payload['infos']
    tick = payload['tick']
    expectedTick = state.tick + 1
    if tick != expectedTick:
        logger.warning(f'chrome {hostId} tick mismatch: expected {expectedTick}, got {tick}, requesting full sync')
        try:
            fullWindows = await state.proxy.sync()
            fullDTOs = _chromeWindowsToDTOs(fullWindows)
            state.prevWindows = fullDTOs
            state.tick = tick
            await _notify([WindowChangeInfo(type='add', data=w) for w in fullDTOs])
            return
        except Exception as e:
            traceback.print_exc()
            return
    state.tick = tick
    await _notify(payload)
import json
def saveStatus(sess,status):
    with open('status.json','w',encoding='utf-8') as f:
        f.write(json.dumps(status,ensure_ascii=False))
    return True
def loadStatus(sess):
    try:
        with open('status.json','r',encoding='utf-8') as f:
            return json.loads(f.read())
    except :
        return None
async def toTop(sess, windowId, system=None):
    if(system==None or system=='win'):
        window_proxy.setTop(windowId)
        return
    for hostId, state in chromeClientStates.items():
        try:
            if(await state.proxy.getHost()==system):
                await state.proxy.toTop(windowId)
        except Exception as e:
            print('chrome totop failed,current id:',system)
            print('exist client:')
            for key in chromeClientStates.keys():
                try:
                    await chromeClientStates[key].proxy.getHost()
                    connecting=True
                except:
                    connecting=False
                print(f'[{key}]:{connecting}')
            traceback.print_exc()
    pass
from ui import getWindow
def exit(sess):
    getWindow().exitSignal.emit()
def expand(sess):
    getWindow().expandSignal.emit()
def collapse(sess):
    getWindow().collapseSignal.emit()

def pin(sess,boolValue):
    from conf import conf
    conf['pin']=boolValue
    return  boolValue

def setAllowRemote(sess,boolValue):
    from conf import conf
    conf['allowRemote']=boolValue
    return boolValue

# ---- softSave / dumpSave ----
_softSaveData = None

def softSave(sess, status):
    """前端定时调用，将数据暂存到内存中"""
    global _softSaveData
    _softSaveData = status
    return True

def dumpSave():
    """将内存中的数据持久化到磁盘"""
    global _softSaveData
    if _softSaveData is None:
        return False
    saveStatus(None, _softSaveData)
    return True