from concurrent.futures import ThreadPoolExecutor
import random
import time

import socks

SUCCESS_LIST: list = []
COUNT = 0


def sock_request_test(sim_conn_lost: bool = False) -> None:
    try:
        s = socks.socksocket()

        s.set_proxy(
            socks.SOCKS5,
            "localhost",
            9011,
            username="username",
            password="password",
        )
        s.connect(("docs.python.org", 80))
        # HACK: www.baidu.com不会自己关闭连接！！！！！！！！！！！
        s.sendall(b"HEAD / HTTP/1.1\r\nHost: docs.python.org\r\n\r\n")

        response = b""
        while 1:
            data = s.recv(4096)
            # print(len(data))

            if data == b"":
                break

            response += data

        # print(response)
        global COUNT
        COUNT += 1
        print(f"{COUNT} Done!")

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
    start = time.time()
    # pool = ProcessPoolExecutor(max_workers=60)  # 60进程，最大并发量
    pool = ThreadPoolExecutor(max_workers=16)
    for i in range(n):
        pool.submit(sock_request_test)
    pool.shutdown(wait=True)
    end = time.time()
    print(f"本轮耗时{end - start}秒")


def stress_test_loop(n: int, times: int = 5):
    """循环压测

    n: 一轮循环的请求总量
    """
    for i in range(times):
        stress_test(n)
        print("-" * 20)
        time.sleep(1)


if __name__ == "__main__":
    sock_request_test()
    # time.sleep(1)
    # stress_test_loop(50, 1000)
