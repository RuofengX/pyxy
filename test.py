from concurrent.futures import ThreadPoolExecutor
from urllib import response
from aisle import LOG as logging
from objprint import op
import socket
import asyncio
import socks

def sockResuestTest():
    s = socks.socksocket()
    
    s.set_proxy(socks.SOCKS5, 'localhost', 9011, username='username', password='password')
    s.connect(('www.baidu.com', 80))
    s.sendall(b'HEAD / HTTP/1.1\r\nHost: www.baidu.com\r\n\r\n')
    
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
    
def stressTest(n: int):
    """socks压力测试"""
    with ThreadPoolExecutor(max_workers=10) as pool:
        for i in range(n):
            future = pool.submit(sockResuestTest)
    
if __name__ == '__main__':
    sockResuestTest()
    # stressTest(1000)


