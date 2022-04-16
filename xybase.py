from __future__ import annotations
from typing import Any, Callable, Coroutine
import gc
import asyncio
import sys
import os
import warnings
from ssl import SSLError
import psutil

import objgraph  # TODO: 内存参考，正式版将会删除

from safe_block import Key
from aisle import LogMixin

ENABLE_UVLOOP = False
try:
    import uvloop

    # 使用uvloop优化事件循环
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    ENABLE_UVLOOP = True
except ImportError as err:
    if sys.platform == "linux":
        warnings.warn(
            f"""uvloop loaded fail. You see this warning because you are running this \
                program on linux, which may supports uvloop module. The uvloop will \
                bring the whole program much faster, please consider install it. \
                Detail debug info: \n{err}
            """
        )
    pass
    # TODO: pypy3.9暂未支持uvloop，参考链接 https://github.com/PyO3/pyo3/issues/2137


class StreamBase(LogMixin):
    """一个异步处理多个流的基类"""

    def __init__(self, key: str, *args, **kwargs):

        gc.disable()

        self.key = Key(key_string=key)

        self.total_conn_count = 0  # 一共处理了多少连接
        self.current_conn_count = 0  # 目前还在保持的连接数

        super().__init__(*args, **kwargs)
        self.logger.set_level("INFO")  # Change Log level here!! 在这里更改日志等级！！

    async def exchange_stream(
        self,
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
            self.logger.error("远程连接提前关闭")
            return

        await asyncio.gather(
            self.__copy(localReader, remoteWriter, debug="upload"),
            self.__copy(remoteReader, localWriter, debug="download"),
            return_exceptions=True,
        )

        self.logger.debug("双向流均已关闭")

    async def __copy(
        self,
        r: asyncio.StreamReader,
        w: asyncio.StreamWriter,
        debug: str = None,
        timeout: int = None,
    ) -> None:
        """异步流拷贝

        r: 源
        w: 目标
        debug: 无视即可
        timeout: 定义了连接多久之后会被回收，如果使用了uvloop则无视该参数
        """
        # HACK: 减小循环内部逻辑使用量和变量数量，同时避免触发日志
        if ENABLE_UVLOOP:
            # 使用uvloop能大幅减小内存使用，将超时设置为TCP默认时间
            while 1:
                try:

                    data = await r.read(4096)  # 不进行超时测试，减少事件调度

                    if not data:
                        break
                    w.write(data)
                    await w.drain()  # 不应节省

                except Exception:
                    break

        else:
            # 性能可能较弱
            timeout = timeout  # 防止使用原生事件循环导致的高内存占用
            while 1:
                try:

                    data = await asyncio.wait_for(r.read(4096), timeout=timeout)

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
                    # 可能有ConnectResetError
                    break

        self.logger.debug(f"开始拷贝流，debug：{debug}")

        await self.try_close(w)

        self.logger.debug(f"拷贝流结束，debug：{debug}")
        return

    @staticmethod
    def handlerDeco(
        coro: Callable[
            [StreamBase, asyncio.StreamReader, asyncio.StreamWriter],
            Coroutine[Any, Any, Any],
        ]
    ) -> Callable[
        [StreamBase, asyncio.StreamReader, asyncio.StreamWriter],
        Coroutine[Any, Any, Any],
    ]:
        """处理连接的装饰器

        接收一个用于连接处理的协程，一般名字叫handle。
        在协程执行前自动增加连接计数，在协程执行后自动减少连接计数
        """

        async def handler(self: StreamBase, *args, **kwargs):

            self.total_conn_count += 1
            self.current_conn_count += 1
            self.logger.debug("开始处理新的连接")
            self.logger.debug(f"当前并发连接数: {self.current_conn_count}")

            rtn = await coro(self, *args, **kwargs)

            self.current_conn_count -= 1
            self.logger.debug("连接处理完毕")
            self.logger.debug(f"当前并发连接数: {self.current_conn_count}")

            if self.current_conn_count == 0:

                # 仅当当前连接数为0时，才释放内存，防止回收还在等待的协程
                gc.collect()
                self.logger.info("GC DONE")
                self.logger.info("对象增量信息：")
                print("-" * 20)
                objgraph.show_growth(shortnames=False)
                print("-" * 20)
                if sys.implementation.name == "pypy":
                    self.logger.warning(
                        f"当前内存状态\n{gc.get_stats()}"
                    )  # 该方法会调用一次gc.collect()
                elif sys.implementation.name == "cpython":
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info().rss  # in bytes
                    self.logger.warning(f"当前内存占用{memory_info / 1024 / 1024:.5}MB")

            return rtn

        return handler

    async def try_close(self, w: asyncio.StreamWriter, timeout: int = None) -> None:
        """尝试关闭连接，直到连接关闭，或超时

        w: asyncio的流写入对象
        timeout: 可选，如果不为None则会给w.wait_closed()协程指定一个超时时长

        捕获所有异常"""

        try:
            if not w.is_closing():
                w.close()

            if timeout:
                asyncio.wait_for(w.wait_closed(), timeout)
            else:
                await w.wait_closed()

            self.logger.info("远程连接已关闭")

        except asyncio.TimeoutError:
            self.logger.warning("在关闭连接时超时")

        except BrokenPipeError:
            # 连接已经被关闭
            pass

        except ConnectionResetError:
            # 连接被重置
            pass

        except SSLError:
            # ssl连接错误，可能是上述错误导致的
            pass

        except Exception as err:
            self.logger.warning(f"在关闭连接时发生意外错误 > {type(err)} {err}")
