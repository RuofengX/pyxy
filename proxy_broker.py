import socket
from struct import pack, unpack
import asyncio
from aisle import LogMixin
from client import Client, RemoteClientError
from xybase import StreamBase
from config_parse import PyxyConfig

# from memory_profiler import profile
SOCKS_VERSION = 5


class SocksError(Exception):
    """Sock协议错误"""

    def __init__(self, msg: str = None):
        super().__init__(msg)
        self.message = msg

    def __str__(self) -> str:
        return f'SocksError: {self.message}'


class SockRelay(StreamBase, LogMixin):
    """维护本地Socks5代理"""

    def __init__(self,
                 config: PyxyConfig,
                 remoteAddr: str,
                 remotePort: int
                 ) -> None:
        super().__init__()

        self.config = config.client
        
        self.username = self.config['username']
        self.password = self.config['password']
        self.sock_proxy_addr = self.config['socks5_address']
        self.sock_proxy_port = self.config['socks5_port']
        self.remote_addr = remoteAddr
        self.remote_port = remotePort
        super().__init__()
        # self.run()

    def run(self):
        """同步启动
        """
        try:
            asyncio.run(self.start_sock_server())
        except KeyboardInterrupt:
            return

    async def start_sock_server(self) -> None:
        """启动Socks5服务器"""
        # TODO: 给Socks连接也加上TLS加密

        server = await asyncio.start_server(
            self.local_sock_handle, self.sock_proxy_addr, self.sock_proxy_port,
            backlog=self.config['backlog'])

        addr = server.sockets[0].getsockname()
        self.logger.warning(f'服务器启动, 端口:{addr[1]}')

        async with server:
            await server.serve_forever()

    @StreamBase.handlerDeco
    async def local_sock_handle(self,
                              reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter
                              ) -> None:
        """处理本地Socks5代理的请求"""

        request_id = self.total_conn_count - 1
        logger = self.logger.get_child(str(request_id))
        logger.debug(f'接收来自{writer.get_extra_info("peername")}的连接')
        try:
            # Socks5参考文献
            # [RFC1928](https://www.quarkay.com/code/383/socks5-protocol-rfc-chinese-traslation )

            # Socks5协议头
            header = await reader.readexactly(2)
            version, nmethods = unpack('!BB', header)
            assert version == SOCKS_VERSION, SocksError('不支持的Socks版本')
            assert nmethods > 0, SocksError('Socks请求包协议头错误，认证方式的数量不能小于0')

            # 检查客户端支持的methods
            methods = []
            for _ in range(nmethods):
                methods.append(ord(await reader.readexactly(1), ))

            # 目前只兼容用户名密码方式
            if not 2 in set(methods):
                raise SocksError('不支持的身份验证方式')

            # 发送支持的methods
            writer.write(pack('!BB', SOCKS_VERSION, 2))  # 2表示用户名密码方式
            await writer.drain()

            # 验证身份信息
            # [文档](https://www.jianshu.com/p/8001c40e5f83)
            version = ord(await reader.readexactly(1))
            assert version == 1, SocksError('不支持的身份验证版本')

            username_len = ord(await reader.readexactly(1))
            username = (await reader.readexactly(username_len)).decode('utf-8')

            password_len = ord(await reader.readexactly(1))
            password = (await reader.readexactly(password_len)).decode('utf-8')

            if (username == self.username) and (password == self.password):
                # 身份验证成功
                writer.write(pack("!BB", version, 0))  # 0 表示正确
                await writer.drain()

            else:
                # 身份验证失败
                writer.write(pack("!BB", version, 0xFF))  # !0 表示不正确
                await writer.drain()
                raise SocksError('身份验证失败')

            # 读取客户端请求
            # request
            version, cmd, _, address_type = unpack("!BBBB", await reader.readexactly(4))
            assert version == SOCKS_VERSION, SocksError('不支持的Socks版本')

            if address_type == 1:  # IPv4
                true_domain = ''
                true_ip_bytes = await reader.readexactly(4)
                if true_ip_bytes == b'':
                    raise SocksError('没有获取到目标IP地址')
                true_ip = socket.inet_ntoa(true_ip_bytes)

            elif address_type == 3:  # 域名
                true_ip = ''
                domain_length = (await reader.readexactly(1))[0]  # 返回int类型
                true_domain_bytes = await reader.readexactly(domain_length)
                true_domain = true_domain_bytes.decode('utf-8')

            else:
                raise SocksError(f'不支持的地址类型{address_type}')

            true_port = unpack('!H', await reader.readexactly(2))[0]
            logger.info(f'客户端请求 > {true_ip}|{true_domain}:{true_port}')

            # 在远程创建真实链接
            remote_client = Client(self.remote_addr, self.remote_port, tag=request_id)
            response = await remote_client.remote_handshake(payload={
                'ip': true_ip,
                'domain': true_domain,
                'port': true_port
            }
            )
            
            bind_address, bind_port = response
            
            if bind_address is None or bind_port is None:
                raise RemoteClientError('远程服务器返回解析错误')
            
            
            bind_address_bytes = socket.inet_aton(bind_address)
            bind_address_int = unpack('!I', bind_address_bytes)[0]

            # 对Socks客户端响应连接的结果
            reply = pack("!BBBBIH", SOCKS_VERSION, 0,
                         0, 1, bind_address_int, bind_port)
            writer.write(reply)
            await writer.drain()

            # 建立数据交换
            if not remote_client.remote_reader:
                raise RemoteClientError('连接未建立')
            if not remote_client.remote_writer:
                raise RemoteClientError('连接未建立')
            
            if reply[1] == 0 and cmd == 1:
                await remote_client.exchange_stream(reader,
                                                   writer,
                                                   remote_client.remote_reader,
                                                   remote_client.remote_writer
                                                   )

        except RemoteClientError as error:
            logger.warning(f'远程创建连接失败 > {error}')

        except SocksError as error:
            logger.warning(f'Socks错误 > {error}')

        except OSError as error:
            logger.warning(f'OS错误 > {error}')

        except Exception as error:
            logger.warning(f'未知错误 > {error}')

        finally:
            try:
                writer.close()
                await writer.wait_closed()
                logger.debug('本地连接已关闭')
            except Exception as error:
                logger.critical(f'关闭本地连接失败 > {error}')

            try:
                await remote_client.remote_close()
            except Exception as error:
                logger.debug(f'关闭远程连接失败 > {error}')

            logger.info('请求处理结束')

            # DEBUG
            # objgraph.show_growth()


if __name__ == '__main__':
    config = PyxyConfig()
    proxy_server = SockRelay(
        config,
        remoteAddr=config.general['domain'],
        remotePort=config.server['port'])
    proxy_server.run()
