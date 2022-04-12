from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from random import Random
import random
import time

import socks
SUCCESS_LIST: list = []
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
        if random.randint(0, 1):  # 模拟连接没有正确关闭
            s.close()
        print(response)
    
def stressTest(n: int):
    """socks压力测试"""
    pool = ProcessPoolExecutor(max_workers=60)
    for i in range(n):
        pool.submit(sockResuestTest)
    pool.shutdown(wait=True)
    
        
            
                
if __name__ == '__main__':
    sockResuestTest()
    # while 1:
    #     stressTest(500)
    #     print('-'*20)
    #     time.sleep(5)


