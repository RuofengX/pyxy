from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from random import Random
import random
import time

import socks
SUCCESS_LIST: list = []
def sock_request_test(sim_conn_lost: bool = False) -> None:
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
        
        print(response)
            
    except Exception as e:
        print(e)
    finally:
        if sim_conn_lost:
            if random.randint(0, 1):  # 模拟连接没有正确关闭
                s.close()
        else:
            s.close()
            
    
def stress_test(n: int):
    """socks压力测试
    
    n: 请求总量
    """
    # pool = ProcessPoolExecutor(max_workers=60)  # 60进程，最大并发量
    pool = ThreadPoolExecutor(max_workers=1000)  # 1000线程，最大并发量
    for i in range(n):
        pool.submit(sock_request_test)
    pool.shutdown(wait=True)
    
        
def stress_test_loop(n: int):
    """循环压测
    
    n: 一轮循环的请求总量
    """
    while 1:
        stress_test(n)
        print('-'*20)
        time.sleep(5)
                
if __name__ == '__main__':
    sock_request_test()
    stress_test_loop(5000)
    
    


