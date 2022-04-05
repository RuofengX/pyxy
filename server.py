# coding: utf-8
import asyncio
from objprint import objstr
from aisle import LOG, LogMixin
from SafeBlock import Block, Key, DecryptError
import shortuuid
import socket


class Server(LogMixin):
    def __init__(self, addr='0.0.0.0', port=9190):
        super().__init__()
        self.key = Key('1b94f71484d0488681ef7c9a625a2069')
        asyncio.run(self.start(addr=addr, port=port))

    async def start(self, addr: str, port):
        """异步入口函数"""
        server = await asyncio.start_server(self.handler, addr, 9190)
        self.logger.warning(f"服务器启动在{addr}:{port}")
        async with server:
            await server.serve_forever()

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理请求，捕获所有的异常"""
        requestId = shortuuid.ShortUUID().random(length=8).upper()
        logger = self.logger.getChild(f'{requestId}')
        isClosed = False
        try:
            
            trueIp, trueDomain, truePort = await self.__exchangeBlock(reader, writer)

            logger.debug(f'收到请求 > {trueIp}|{trueDomain}:{truePort}')
            
            if (not trueIp) and (not trueDomain):
                logger.error(f'没有提供ip或domain')
                raise ValueError('没有提供ip或domain')

            if trueDomain:
                trueIp = socket.gethostbyname(trueDomain)

            
            trueReader, trueWriter = await asyncio.open_connection(trueIp, truePort)
            
            bindAddress, bindPort = trueWriter.get_extra_info('sockname')
            pass
        
            await self.__exchangeBlock(reader, writer, {
                'bindAddress': bindAddress,
                'bindPort': bindPort
            })
            
            await self.__remoteExchangeStream(
                lr=reader,
                lw=writer,
                rr=trueReader,
                rw=trueWriter
            )
            
        except socket.gaierror as e:
            logger.error(f'解析域名失败 > {e}')
        
        
        except ConnectionResetError as e:
            isClosed =True
            logger.warning(f'连接意外关闭 > {e}')
            return
        
        except Exception as e:
            logger.error(f"未知错误 > {type(e)} {e}")


        finally:
            if isClosed:
                logger.debug(f'请求处理结束')
                return
            try:
                logger.debug(f'尝试关闭请求')
                writer.close()
                await writer.wait_closed()
                logger.debug(f'请求处理结束')
            except Exception as e:
                logger.warning(f'在关闭请求的过程中发生了其他错误 > {objstr(e)}')
                pass

    async def __exchangeBlock(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, payload: dict=None):
        '''远程的连接预协商'''
        if payload:
            '''发送'''
            request = Block(self.key, payload)
            writer.write(request.blockBytes)
            await writer.drain()
            return 
        
        else:
            '''接收'''
            try:
                requeset = await reader.read(4096)
                block = Block.fromBytes(self.key, requeset)
                trueIp = block.payload['ip']
                trueDomain = block.payload['domain']
                truePort = block.payload['port']
                # self.logger.debug(f'收到客户端请求 {trueDomain} | {trueIp}:{truePort}')
                
                return trueIp, trueDomain, truePort
            
            except DecryptError as e:
                # self.logger.error(f'解密失败, {e}')
                raise e
            
            except KeyError as e:
                # self.logger.error(f'加密方式正确，但请求无效, {e}')
                raise e
            
            except Exception as e:
                # self.logger.error(f'预协商失败, {e}')
                raise e

    async def __remoteExchangeStream(self, 
                                   lr: asyncio.StreamReader, 
                                   lw: asyncio.StreamWriter,
                                   rr: asyncio.StreamReader,
                                   rw: asyncio.StreamWriter
                                   ):
        await asyncio.gather(
            self.__copy(lr, rw),
            self.__copy(rr, lw))
            
        lw.close()
        rw.close()
        await lw.wait_closed()
        await rw.wait_closed()
        

    

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
    server = Server()
