# coding: utf-8
import asyncio
import socket
import ssl
from safe_block import Block, DecryptError
from xybase import StreamBase
from aisle import SyncLogger


class Server(StreamBase):
    """服务器对象"""

    def __init__(self):
        super().__init__()

        # 获取安全环境
        self.safe_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.safe_context.load_cert_chain(
            certfile='./certs/pyxy.s-2.link_bundle.crt', keyfile='./certs/pyxy.s-2.link.key')
        # You can load your own cert and key files here.

    async def start(self, addr: str, port, backlog: int=8192):
        """异步入口函数
        
        addr: 连接监听地址
        port: 连接监听端口
        backlog: 监听队列长度，超过这个数量的并发连接将被拒绝
        """
        self.logger: SyncLogger = self.logger.get_child(f'{addr}:{port}')
        server = await asyncio.start_server(self.handler,
                                            addr,
                                            9190,
                                            # limit=4096,  # 创建的流的缓冲大小
                                            ssl=self.safe_context,
                                            backlog=backlog
                                            )
        self.logger.warning(f"Server starting at {addr}:{port}")
        async with server:
            await server.serve_forever()

    @StreamBase.handlerDeco
    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理请求，捕获所有的异常"""
        
        request_id = self.total_conn_count
        logger = self.logger.get_child(f'{request_id}')
        try:
            # 请求处理主体

            # 1. 预协商
            true_ip, true_domain, true_port = await self.__exchange_block(reader, writer)
            logger.info(f'Get request > {true_ip}|{true_domain}:{true_port}')

            # 2. 格式化目标地址
            if (not true_ip) and (not true_domain):
                logger.error('NO IP OR DOMAIN')
                raise ValueError('NO IP OR DOMAIN')

            if true_domain:
                true_ip = socket.gethostbyname(true_domain)
            logger.info(
                f'Start true connect > {true_ip}|{true_domain}:{true_port}')

            # 3. 尝试建立真实连接
            bind_address, bind_port = '', 0
            try:
                true_reader, true_writer = await asyncio.open_connection(true_ip, true_port)

                bind_address, bind_port = true_writer.get_extra_info(
                    'sockname')

            except Exception as error:
                logger.warning(f'Unexpected error > {type(error)}:{error}')
                raise error

            finally:
                await self.__exchange_block(reader, writer, {
                    'bind_address': bind_address,
                    'bind_port': bind_port
                })

            # 4. 开始转发
            await self.exchange_stream(
                reader,
                writer,
                true_reader,
                true_writer
            )

        # 全部流程的异常处理
        except socket.gaierror as error:
            logger.error(f'DNS failure > {error}')

        except ConnectionResetError as error:
            logger.warning(f'Connection Reset > {error}')
            return
        except ConnectionRefusedError as error:
            logger.warning(f'Connection Refused > {error}')

        except TimeoutError as error:
            logger.warning(f'Connection timeout > {error}')

        except OSError as error:
            logger.warning(f'System fail connection > {error}')

        except Exception as error:
            logger.error(f"Unknown error > {type(error)} {error}")

        finally:
            await asyncio.gather(
                self.try_close(true_writer),
                self.try_close(writer)
            )

            # 收尾工作
            logger.debug('Request Handle End')

    async def __exchange_block(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, payload: dict = None):
        '''远程的连接预协商'''
        if payload:
            # 发送
            request = Block(self.key, payload)
            writer.write(request.block_bytes)
            await writer.drain()
            return

        else:
            # 接收
            try:
                response = await reader.read(4096)
                block = Block.from_bytes(self.key, response)
                true_ip = block.payload['ip']
                true_domain = block.payload['domain']
                true_port = block.payload['port']
                # self.logger.debug(f'收到客户端请求 {trueDomain} | {trueIp}:{truePort}')

                return true_ip, true_domain, true_port

            except DecryptError as error:
                # self.logger.error(f'解密失败, {e}')
                raise error

            except KeyError as error:
                # self.logger.error(f'加密方式正确，但请求无效, {e}')
                raise error

            except Exception as error:
                # self.logger.error(f'预协商失败, {e}')
                raise error


if __name__ == '__main__':
    serverIPv4 = Server()
    serverIPv6 = Server()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.gather(
            serverIPv4.start('0.0.0.0', 9190)
        )
    )
