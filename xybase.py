import gc
import asyncio
import objgraph
from setuptools import find_packages



from SafeBlock import Key
from aisle import LogMixin


class StreamBase(LogMixin):
    def __init__(self, *args, **kwargs):
        gc.disable()  # 关闭垃圾回收
        
        self.totalConnections = 0  # 一共处理了多少连接
        self.currentConnections = 0  # 目前还在保持的连接数
        
        with open('key', 'rt') as f:
            keyStr = f.readline().strip()
        keyStr = keyStr.replace('\n', '')
        self.key = Key(keyStr)
        
        super().__init__(*args, **kwargs)

    async def exchangeStream(self,
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
                     debug: str = None
                     ) -> None:
        """异步流拷贝
        
        r: 源
        w: 目标
        debug: 无视即可
        """
        debugCount = 0
        self.logger.debug(f'开始拷贝流，debug：{debug}')
        while 1:
            debugCount += 1
            try:

                if r.at_eof():
                    break

                data = await asyncio.wait_for(
                    r.read(4096),  # 如果仅仅使用read的话，循环会一直卡在await
                    timeout=2.05
                )
                if data == b'' and r.at_eof():
                    break
                # self.logger.debug(f'{r.at_eof()}')
                w.write(data)
                await w.drain()

            except Exception as v:
                self.logger.debug(f'远程连接中止 {v}')
                break
        
        w.close()
        await w.wait_closed()
        self.logger.debug(f'拷贝流结束，debug：{debug}')
        return

    @staticmethod
    def handlerDeco(coro: asyncio.coroutine) -> asyncio.coroutine:
        """处理连接的装饰器

        接收一个协程，在协程执行前自动增加连接计数，在协程执行后自动减少连接计数
        """
        async def handler(self: StreamBase, *args, **kwargs):
            
            self.totalConnections += 1
            self.currentConnections += 1
            self.logger.debug(f'当前连接数: {self.currentConnections}')
            
            
            rtn = await coro(self, *args, **kwargs)
            
            
            self.currentConnections -= 1
            self.logger.info(f'当前连接数: {self.currentConnections}')
            
            if self.currentConnections == 0:
                # 仅当当前连接数为0时，才释放内存，防止回收还在等待的协程
                # _m = len(gc.get_objects(generation=2))
                gc.collect()
                self.logger.info(f'垃圾回收，当前内存状态\n{gc.get_stats(memory_pressure=False)}')
                
                
                
        
            return rtn
        
        return handler
    