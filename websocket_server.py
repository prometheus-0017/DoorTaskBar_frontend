
import asyncio
import websockets
import json
import rpc_content
from xuri_rpc_websocket import createServer

# setHostId('taskbarBackend')
# getMessageReceiver().setObject('rpc',rpc_content,True)

# hostId2Websocket:dict[str,websockets.WebSocketServerProtocol]={}
# hostId2Sender:dict[str,ISender]={}

# class Sender(ISender):
#     def __init__(self,remoteHostId,websocket):
#         # self.websocket=websocket
#         hostId2Websocket[remoteHostId]=websocket
#         self.remoteHostId=remoteHostId

#     async def send(self,message:Message):
#         socket= hostId2Websocket.get(self.remoteHostId)
#         if(socket==None):
#             raise Exception('websocket is closed')
#         await socket.send(json.dumps(message))
# from typing import cast
# #todo add xuri_rpc Request
# from xuri_rpc import Request
# async def onMessageReceived(websocket, path):
#     sender=None
#     async for msg in websocket:
#         message:Message=json.loads(msg)
#         client=Client()
#         def isRequest(message:Message):
#             return message.get('idFor')==None
#         if(isRequest(message)):
#             request=cast(Request,message)
#             remoteHostId=request['meta'].get('hostId')
#             sender=Sender(remoteHostId,websocket)
#         else:
#             if(sender==None):
#                 print("warnning: sender is None")
#         if(sender==None):
#             return
        
#         client.setSender(sender)
#         asyncio.ensure_future(getMessageReceiver().onReceiveMessage(message,client))
#         # getMessageReceiver().onMessageReceived(message,Client(Sender(websocket)))

import conf
from typing import cast
from util import messageBox,is_port_in_use
import sys
import lock
def startWebSocket():
    
    if(is_port_in_use(conf.get('websocketPort'))):
        messageBox(f'{conf.get("websocketPort")}端口被占用')
        sys.exit(1)

    lock.setOK(lock.FLAG_WEBSOCKET)
    lock.waitForCheck()
    print('websocket continue')

    
    #创建当前线程async loop
    print('trying starting')
    loop=asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rpc_content.startWindowsDetectLoop()
    async def run():
        serve,_,receiver=await createServer('backend','0.0.0.0',cast(int,conf.get('websocketPort')),'/')
        mainPlaceHolder=object()
        receiver.setObject('rpc',rpc_content,True)
        await serve(mainPlaceHolder)
    # start_server = websockets.serve(onMessageReceived, "0.0.0.0", conf.get('websocketPort'))
    asyncio.get_event_loop().run_until_complete(run())
    asyncio.get_event_loop().run_forever()
if(__name__=='__main__'):
    startWebSocket()
    # main()