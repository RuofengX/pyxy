# coding: utf-8
import asyncio
import socket
import ssl
from SafeBlock import Block, DecryptError
from xybase import StreamBase


class Server(StreamBase):
    def __init__(self):
        super().__init__()

        # 获取安全环境
        self.safeContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.safeContext.load_cert_chain(
            certfile='./certs/pyxy.s-2.link_bundle.crt', keyfile='./certs/pyxy.s-2.link.key')
        # You can load your own cert and key files here.

    async def start(self, addr: str, port):
        """异步入口函数"""
        self.logger = self.logger.get_child(f'{addr}:{port}')
        server = await asyncio.start_server(self.handler, 
                                            addr, 
                                            9190,
                                            ssl=self.safeContext,
                                            backlog=8192)
        self.logger.warning(f"Server starting at {addr}:{port}")
        async with server:  # 需要学习async with
            await server.serve_forever()

    @StreamBase.handlerDeco
    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理请求，捕获所有的异常"""
        # TODO: FOR DEBUG，需要单独做到线程中
        requestId = self.totalConnections
        logger = self.logger.get_child(f'{requestId}')
        try:
            """请求处理主体"""

            # 1. 预协商
            trueIp, trueDomain, truePort = await self.__exchangeBlock(reader, writer)
            logger.info(f'Get request > {trueIp}|{trueDomain}:{truePort}')

            # 2. 格式化目标地址
            if (not trueIp) and (not trueDomain):
                logger.error(f'NO IP OR DOMAIN')
                raise ValueError('NO IP OR DOMAIN')

            if trueDomain:
                trueIp = socket.gethostbyname(trueDomain)
            logger.info(
                f'Start true connect > {trueIp}|{trueDomain}:{truePort}')

            # 3. 尝试建立真实连接
            try:
                trueReader, trueWriter = await asyncio.open_connection(trueIp, truePort)

                bindAddress, bindPort = trueWriter.get_extra_info('sockname')
                pass

            except Exception as e:
                logger.warning(f'Unexpected error > {type(e)}:{e}')
                bindAddress = ''
                bindPort = 0
                raise e
            finally:
                await self.__exchangeBlock(reader, writer, {
                    'bindAddress': bindAddress,
                    'bindPort': bindPort
                })

            # 4. 开始转发
            await self.exchangeStream(
                reader,
                writer,
                trueReader,
                trueWriter
            )

        # 全部流程的异常处理
        except socket.gaierror as e:
            logger.error(f'DNS failure > {e}')

        except ConnectionResetError as e:
            logger.warning(f'Connection Reset > {e}')
            return
        except ConnectionRefusedError as e:
            logger.warning(f'Connection Refused > {e}')

        except TimeoutError as e:
            logger.warning(f'Connection timeout > {e}')

        except OSError as e:
            logger.warning(f'System fail connection > {e}')

        except Exception as e:
            logger.error(f"Unkown error > {type(e)} {e}")

        finally:
            try:
                """尝试关闭和客户端的连接"""
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                self.logger.debug(
                    f'Close client connection error > {type(e)}:{e}')
                pass
            try:
                """尝试关闭真实连接"""
                trueWriter.close()
                await trueWriter.wait_closed()
            except Exception as e:
                self.logger.debug(
                    f'Close true connection error > {type(e)}:{e}')
                pass

            """收尾工作"""       
            logger.debug(f'Request Handle End')
                   
            return


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


if __name__ == '__main__':
    serverIPv4 = Server()
    serverIPv6 = Server()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.gather(
            serverIPv4.start('0.0.0.0', 9190)
        )
    )
