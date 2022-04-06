from codecs import StreamWriter
import asyncio
from typing import Tuple
from SafeBlock import Key, Block, DecryptError
from aisle import LOG, LogMixin


class RemoteClientError(Exception):
    pass


class Client(LogMixin):
    """维护和远程的连接"""

    def __init__(self, remoteAddr: str = 'localhost', remotePort: int = 9190, tag:str=None) -> None:
        super().__init__()
        if tag is not None:
            self.renameLogger(f'Client-{tag}')
        
        with open('key', 'rt') as f:
            keyStr = f.readline().strip()
        keyStr = keyStr.replace('\n', '')
        
        self.key = Key(keyStr)
        self.remoteAddr = remoteAddr
        self.remotePort = remotePort

    async def remoteHandshake(self, payload: dict) -> tuple:
        '''打开一个连接之前的预协商'''
        block = Block(self.key, payload)
        try:
            response = await self.__exchangeBlock(block.blockBytes)
            rtn = None
            responseBlock = Block.fromBytes(self.key, response)
            
            bindAddress, bindPort = responseBlock.payload['bindAddress'], responseBlock.payload['bindPort']
            self.logger.debug(f'预协商成功')
            if (bindAddress == '') or (bindPort == 0):
                raise RemoteClientError('远程连接建立失败')
            
            rtn = bindAddress, bindPort
            self.logger.debug(f'远程已创建连接，地址：{bindAddress}，端口：{bindPort}')

        except ConnectionResetError as e:
            self.logger.error(f'远程连接关闭')
            await self.remoteClose()

        except DecryptError as e:
            self.logger.error(f'预协商解密时发生错误{e}')
            await self.remoteClose()

        except Exception as e:
            self.logger.error(f'预协商时发生错误{e}')
            await self.remoteClose()

        finally:
            """不关闭连接"""
            return rtn

    async def remoteExchangeStream(self, localReader: asyncio.StreamReader, localWriter: StreamWriter) -> None:
        """和远程交换流上的数据"""
        
        if not self.remoteWriter:
            self.logger.error('远程连接提前关闭')
            return
        
        result = await asyncio.gather(
            self.__copy(localReader, self.remoteWriter),
            self.__copy(self.remoteReader, localWriter),
            return_exceptions=True
        )
        for r in result:
            if not r:
                self.logger.warn(f'异步的数据交换返回了异常的结果 > {r}')
            
        self.logger.debug(f'双向流均已关闭')
        await self.remoteClose()

    async def remoteClose(self) -> None:
        if not self.remoteWriter:
            self.logger.error('无法关闭一个不存在的远程连接')
            return
        self.remoteWriter.close()
        await self.remoteWriter.wait_closed()
        self.logger.debug('远程连接已关闭')

    async def __exchangeBlock(self, raw: bytes) -> bytes:
        '''远程的连接预协商，self.reader和writer初始化'''
        self.remoteReader, self.remoteWriter = await self.__connect()

        self.remoteWriter.write(raw)
        await self.remoteWriter.drain()
        rtn = await self.remoteReader.read(4096)

        return rtn

    async def __connect(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection(
            self.remoteAddr, self.remotePort,
            ssl=True)

    async def __copy(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        """将r中的数据写入w"""
        while 1:
            data = await r.read(4096)  # 这里阻塞了，等待本地的数据
            if not data:
                w.write_eof()
                await w.drain()
                break
            
            w.write(data)
            await w.drain()
        return


if __name__ == '__main__':
    client = Client()
