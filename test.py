from urllib import response
from aisle import LOG as logging
from objprint import op
import socket

import socks

def sockResuestTest():
    s = socks.socksocket()
    
    s.set_proxy(socks.SOCKS5, 'localhost', 9011, username='username', password='password')
    s.connect(('www.tencent.com', 80))
    s.sendall(b'GET /index.html HTTP/1.1 \r\n\r\n')
    
    response = b''
    while 1:
        data = s.recv(4096)
        print(len(data))
        
        if data[-4:] == b'\r\n\r\n':
            response += data
            break
        
        if data == b'':
            break
        
        response += data
    s.close()
    print(response)
if __name__ == '__main__':
    sockResuestTest()


