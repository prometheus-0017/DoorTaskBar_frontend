from threading import Lock
lock=Lock()
status={}
PORT_READY=2
SERVICE_READY=3

FLAG_WEBSOCKET='ws'
FLAG_HTTP='http'
FLAG_HTTP_START='http_start'

def setOK(flagName):
    with lock:
        status[flagName]=True
    print(flagName,'ok')
    
from time import sleep
def waitForOk(expression):
    while not expression():
        sleep(0.1)
    return 
def waitForCheck():
    return waitForOk(lambda: status.get(FLAG_WEBSOCKET) and status.get(FLAG_HTTP))
def waitForStart():
    return waitForOk(lambda: status.get(FLAG_HTTP_START))
    
