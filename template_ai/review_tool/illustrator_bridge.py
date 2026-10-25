"""Retired uncontained COM route. Use the isolated native reader."""
class BridgeError(ValueError):
    pass

def available():
    return False

class IllustratorBridge:
    def __init__(self,*args,**kwargs):
        raise BridgeError('Illustrator 視窗接口已停用；請使用一般加入檔案與離線原生判讀。')
