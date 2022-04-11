from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing import Queue
from threading import Thread 
from urllib import response
from aisle import LOG as logging
from objprint import op
import socket
import asyncio
import socks
SUCCESS_LIST = []
def sockResuestTest():
    try:
        s = socks.socksocket()
    
        s.set_proxy(socks.SOCKS5, 'localhost', 9011, username='username', password='password')
        s.connect(('www.baidu.com', 80))
        s.sendall(b'HEAD / HTTP/1.1\r\nHost: www.baidu.com\r\n\r\n')
        
        response = b''
        while 1:
            data = s.recv(4096)
            # print(len(data))
            
            if data == b'':
                break
            
            response += data
            
    except Exception as e:
        print(e)
    finally:
        s.close()
        print(response)
    
def stressTest(n: int):
    """socks压力测试"""
    pool = ThreadPoolExecutor(max_workers=100)
    for i in range(n):
        pool.submit(sockResuestTest)
    pool.shutdown(wait=True)
    
        
            
                
if __name__ == '__main__':
    # sockResuestTest()
    
    stressTest(100)


