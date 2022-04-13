"""
Filename: client.py
"""
import asyncio
import copy
from typing import Tuple, Coroutine
from safe_block import Block, DecryptError
from xybase import StreamBase
from aisle import SyncLogger


class RemoteClientError(Exception):
    """和远程连接的客户端对象错误"""

    def __init__(self, msg: str = None):
        super().__init__(msg)
        self.message = msg

    def __str__(self) -> str:
        return f'RemoteClientError: {self.message}'


class Client(StreamBase):
    """维护和远程的连接"""

    def __init__(self,
                 remoteAddr: str = 'localhost',
                 remotePort: int = 9190,
                 tag: str = None
                 ) -> None:
        super().__init__()
        if tag:
            self.logger: SyncLogger = self.logger.getChild(f'{tag}')
        self.remote_addr = remoteAddr
        self.remote_port = remotePort
        self.remote_reader: asyncio.StreamReader
        self.remote_writer: asyncio.StreamWriter

    # HACK: 需要优化内存，减小长连接的内存占用

    async def remote_handshake(self, payload: dict) -> tuple:
        '''打开一个连接之前的预协商'''

        try:
            with Block(self.key, payload) as block:
                response = await self.__exchange_block(copy.copy(block.block_bytes))

            response_block = Block.from_bytes(self.key, response)

            bind_address, bind_port = response_block.payload[
                'bind_address'], response_block.payload['bind_port']
            self.logger.debug('预协商成功')
            if (bind_address == '') or (bind_port == 0):
                raise RemoteClientError('远程的连接建立失败')

            rtn = bind_address, bind_port
            self.logger.debug(f'远程已创建连接，地址：{bind_address}，端口：{bind_port}')
            return rtn

        except ConnectionResetError:
            self.logger.debug(f'远程连接关闭')
            await self.remote_close()
            return None, None

        except DecryptError as error:
            self.logger.debug(f'预协商解密时发生错误 {error}')
            await self.remote_close()
            return None, None

        except Exception as error:
            self.logger.warning(f'{error}')
            await self.remote_close()
            return None, None

    async def remote_close(self) -> None:
        """关闭远程的连接
        
        捕获所有异常"""
        await self.try_close(self.remote_writer)
            
    async def __exchange_block(self, raw: bytes) -> bytes:
        '''远程的连接预协商，self.reader和writer初始化'''
        self.remote_reader, self.remote_writer = await self.__connect()

        self.remote_writer.write(raw)
        await self.remote_writer.drain()
        rtn = await self.remote_reader.read(4096)

        return rtn

    async def __connect(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection(
            self.remote_addr, self.remote_port,
            # limit=4096,
            ssl=True)


if __name__ == '__main__':
    client = Client()
