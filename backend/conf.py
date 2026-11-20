conf=dict(pin=False,httpPort=15000,websocketPort=18765,allowRemote=False)

def _loadPersisted():
    try:
        import json
        with open('status.json','r',encoding='utf-8') as f:
            data=json.loads(f.read())
        persisted=data.get('config',{})
        if 'allowRemote' in persisted:
            conf['allowRemote']=persisted['allowRemote']
    except Exception:
        pass
_loadPersisted()

def get(key):
    return conf.get(key)