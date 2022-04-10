from concurrent.futures import ThreadPoolExecutor
from urllib import response
from aisle import LOG as logging
from objprint import op
import socket
import asyncio
import socks
SUCCESS_LIST = []
def sockResuestTest(cb:callable=None, *args, **kwargs):
    s = socks.socksocket()
    
    s.set_proxy(socks.SOCKS5, 'localhost', 9011, username='username', password='password')
    s.connect(('www.baidu.com', 80))
    s.sendall(b'HEAD / HTTP/1.1\r\nHost: www.baidu.com\r\n\r\n')
    
    response = b''
    while 1:
        data = s.recv(4096)
        # print(len(data))
        
        if data[-4:] == b'\r\n\r\n':
            response += data
            break
        
        if data == b'':
            break
        
        response += data
    s.close()
    print(response)
    if cb is not None:
        cb(*args, **kwargs)
    
def stressTest(n: int):
    """socks压力测试"""
    pool = ThreadPoolExecutor(max_workers=8)
    
    def cb(ls:list):
        ls.append(len(ls))
        
    successList = []
    for i in range(n):
        print(i)
        pool.submit(sockResuestTest, cb, successList)
    
    pool.shutdown(wait=True)
    
    for i in range(n):
        if i not in successList:
            print(f'{i} fail')
            
    print(successList)
    
if __name__ == '__main__':
    # sockResuestTest()
    stressTest(10)


