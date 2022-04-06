# coding: utf-8
import asyncio
from sqlite3 import Time
from objprint import objstr
from aisle import LOG, LogMixin
from SafeBlock import Block, Key, DecryptError
import shortuuid
import socket
import sys
import time
import ssl


class Server(LogMixin):
    def __init__(self):
        super().__init__()
        self.key = Key('1b94f71484d0488681ef7c9a625a2069')
        self.connections = 0

        self.__count = 0

        # 获取安全环境
        self.safeContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.safeContext.load_cert_chain(
            certfile='./certs/pyxy.s-2.link_bundle.crt', keyfile='./certs/pyxy.s-2.link.key')

    async def start(self, addr: str, port):
        """异步入口函数"""
        self.renameLogger(f'Server-{addr}:{port}')
        server = await asyncio.start_server(self.handler, addr, 9190,
                                            ssl=self.safeContext)
        self.logger.warning(f"服务器启动在{addr}:{port}")
        async with server:  # 需要学习async with
            await server.serve_forever()

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理请求，捕获所有的异常"""
        self.connections += 1
        # TODO: FOR DEBUG，需要单独做到线程中
        self.logger.info(f'当前连接数：{self.connections}')
        requestId = self.requestCount
        logger = self.logger.getChild(f'{requestId}')
        isClosed = False  # 标记连接是否已经关闭
        try:
            try:
                """尝试建立真实连接"""
                trueIp, trueDomain, truePort = await self.__exchangeBlock(reader, writer)

                logger.info(f'收到请求 > {trueIp}|{trueDomain}:{truePort}')

                if (not trueIp) and (not trueDomain):
                    logger.error(f'没有提供ip或domain')
                    raise ValueError('没有提供ip或domain')

                if trueDomain:
                    trueIp = socket.gethostbyname(trueDomain)

                logger.info(f'开始连接 > {trueIp}|{trueDomain}:{truePort}')

                trueReader, trueWriter = await asyncio.open_connection(trueIp, truePort)

                bindAddress, bindPort = trueWriter.get_extra_info('sockname')
                pass

            except Exception as e:
                logger.warning(f'发生未捕获的错误，请与开发者联系')
                logger.warning(f'建立真实连接时发生错误 > {type(e)}:{e}')
                bindAddress = ''
                bindPort = 0
                raise e

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
            isClosed = True
            logger.warning(f'连接意外关闭 > {e}')
            return
        except ConnectionRefusedError as e:
            isClosed = True
            logger.warning(f'连接被拒绝')

        except OSError as e:
            isClosed = True
            logger.warning(f'连接被拒绝 > {e}')

        except TimeoutError as e:
            isClosed = True
            logger.warning(f'连接超时 > {e}')
            
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
            finally:
                self.connections -= 1
                # TODO: FOR DEBUG
                self.logger.info(f'当前连接数：{self.connections}')

    @property
    def requestCount(self):
        """返回该服务器处理的请求总量"""
        self.__count += 1
        return self.__count

    async def __exchangeBlock(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, payload: dict = None):
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
                w.close()
                await w.wait_closed()
                break

            w.write(data)
            await w.drain()
        return


if __name__ == '__main__':
    serverIPv4 = Server()
    serverIPv6 = Server()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.gather(
            serverIPv4.start('0.0.0.0', 9190)
        )
    )
