import socket
_original_connect=socket.socket.connect
_original_connect_ex=socket.socket.connect_ex
def check(address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1','::1','localhost'):
        raise RuntimeError('AUDIT_EXTERNAL_NETWORK_BLOCKED')
def connect(self,address):
    check(address)
    return _original_connect(self,address)
def connect_ex(self,address):
    check(address)
    return _original_connect_ex(self,address)
socket.socket.connect=connect
socket.socket.connect_ex=connect_ex
