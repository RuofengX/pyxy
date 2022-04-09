from codecs import StreamWriter
import asyncio
from typing import Tuple
from SafeBlock import Key, Block, DecryptError
from aisle import LOG, LogMixin
from xybase import StreamBase
import copy
import sys


class RemoteClientError(Exception):
    pass


class Client(StreamBase):
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

    # HACK: 需要优化内存，减小长连接的内存占用
    async def remoteHandshake(self, payload: dict) -> tuple:
        '''打开一个连接之前的预协商'''
        try:
            with Block(self.key, payload) as block:
                response = await self.__exchangeBlock(copy.copy(block.blockBytes))
            
            # block = Block(self.key, payload)
            # response = await self.__exchangeBlock(copy.copy(block.blockBytes))
            # del block
            
            rtn = None
            responseBlock = Block.fromBytes(self.key, response)
            
            bindAddress, bindPort = responseBlock.payload['bindAddress'], responseBlock.payload['bindPort']
            self.logger.debug(f'预协商成功')
            if (bindAddress == '') or (bindPort == 0):
                raise RemoteClientError('远程的连接建立失败')
            
            rtn = bindAddress, bindPort
            self.logger.debug(f'远程已创建连接，地址：{bindAddress}，端口：{bindPort}')

        except ConnectionResetError as e:
            self.logger.debug(f'远程连接关闭')
            await self.remoteClose()

        except DecryptError as e:
            self.logger.debug(f'预协商解密时发生错误 {e}')
            await self.remoteClose()

        except Exception as e:
            self.logger.debug(f'{e}')
            await self.remoteClose()

        finally:
            """不关闭连接"""
            return rtn


    async def remoteClose(self) -> None:
        if not self.remoteWriter:
            self.logger.warning('无法关闭一个不存在的远程连接')
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



if __name__ == '__main__':
    client = Client()
