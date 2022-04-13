
from __future__ import annotations
from typing import Any, Callable, Coroutine
import gc
import asyncio
import sys
import os
import warnings

import objgraph  # TODO: 内存参考，正式版将会删除

from safe_block import Key
from aisle import LogMixin

try:
    import uvloop
    # 使用uvloop优化事件循环
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError as err:
    if sys.platform == 'linux':
        warnings.warn(f'''uvloop loaded fail. You see this warning because you are running this program on linux, which may supports uvloop module.
                      uvloop will bring the whole program much faster, please consider install it.
                      Detail debug info: {err}
                      ''')
    pass
    # TODO: pypy3.9暂未支持uvloop，参考链接 https://github.com/PyO3/pyo3/issues/2137


class StreamBase(LogMixin):
    """一个异步处理多个流的基类"""

    def __init__(self, *args, **kwargs):

        # gc.disable()

        self.total_conn_count = 0  # 一共处理了多少连接
        self.current_conn_count = 0  # 目前还在保持的连接数

        with open('key', 'rt') as f:
            keyStr = f.readline().strip()
        keyStr = keyStr.replace('\n', '')
        self.key = Key(keyStr)

        super().__init__(*args, **kwargs)
        self.logger.set_level('WARNING')

    async def exchange_stream(self,
                              localReader: asyncio.StreamReader,
                              localWriter: asyncio.StreamWriter,
                              remoteReader: asyncio.StreamReader,
                              remoteWriter: asyncio.StreamWriter,
                              ) -> None:
        """异步双工流交换

        localReader: 本地读取流
        localWriter: 本地写入流
        remoteReader: 远程读取流
        remoteWriter: 远程写入流
        """

        if not remoteWriter:
            self.logger.error('远程连接提前关闭')
            return

        await asyncio.gather(
            self.__copy(localReader, remoteWriter, debug='upload'),
            self.__copy(remoteReader, localWriter, debug='download'),
            return_exceptions=True
        )

        self.logger.debug(f'双向流均已关闭')

    async def __copy(self,
                     r: asyncio.StreamReader,
                     w: asyncio.StreamWriter,
                     debug: str = None,
                    #  timeout=2.05
                    timeout=15
                     ) -> None:
        """异步流拷贝

        r: 源
        w: 目标
        debug: 无视即可
        timeout: 定义了连接多久之后会被回收
        """
        # self.logger.debug(f'开始拷贝流，debug：{debug}')
        while 1:
            # HACK: 主要性能瓶颈
            # 不适用logger进行日志操作以提升效能
            # 捕获所有异常以减少逻辑判断
            # 减少变量使用
            try:

                data = await asyncio.wait_for(
                    r.read(4096),  
                    timeout=timeout
                )
                
                # 不进行超时检测，会导致连接一直保持，直到某一方的下层连接超时断开（一般是60秒）
                # 例如www.baidu.com:80默认不会断开连接，导致大量空连接堆积造成性能下降
                # data = await r.read(4096)  

                if not data:
                    break
                # self.logger.debug(f'{r.at_eof()}')
                
                w.write(data)
                await w.drain()  # 不应节省

            # except asyncio.TimeoutError:
            #     # self.logger.debug(f'连接超时')
            #     break

            except Exception:
                break

        w.close()
        await w.wait_closed()  # 不应节省
        # self.logger.debug(f'拷贝流结束，debug：{debug}')
        return

    @staticmethod
    def handlerDeco(coro: Callable[[StreamBase, asyncio.StreamReader, asyncio.StreamWriter], Coroutine[Any, Any, Any]])\
            -> Callable[[StreamBase, asyncio.StreamReader, asyncio.StreamWriter], Coroutine[Any, Any, Any]]:
        """处理连接的装饰器

        接收一个用于连接处理的协程，一般名字叫handle。
        在协程执行前自动增加连接计数，在协程执行后自动减少连接计数
        """
        async def handler(self: StreamBase, *args, **kwargs):

            self.total_conn_count += 1
            self.current_conn_count += 1
            self.logger.debug('开始处理新的连接')
            self.logger.debug(f'当前并发连接数: {self.current_conn_count}')

            rtn = await coro(self, *args, **kwargs)

            self.current_conn_count -= 1
            self.logger.debug('连接处理完毕')
            self.logger.debug(f'当前并发连接数: {self.current_conn_count}')

            if self.current_conn_count == 0:
                objgraph.show_growth(shortnames=False)  # TODO: 正式版删除
                print('-------------------')

                # 仅当当前连接数为0时，才释放内存，防止回收还在等待的协程
                # gc.collect()

                self.logger.warning(f'垃圾回收完成，当前内存状态\n{gc.get_stats()}')
                # objgraph.show_growth()
                # objgraph.show_growth()

            return rtn

        return handler
