import gc
import socket
from client import Client, RemoteClientError
from pyxy import SOCKS_VERSION
from aisle import LogMixin
from struct import pack, unpack
import asyncio

from xybase import StreamBase

# from memory_profiler import profile

class SocksError(Exception):
    pass


class SockRelay(StreamBase, LogMixin):
    """维护本地Socks5代理"""
    username = 'username'
    password = 'password'
    SOCKS_VERSION = 5

    def __init__(self,
                 sockProxyAddr: str = 'localhost',
                 sockProxyPort: int = 9011,
                 remoteAddr: str = 'localhost',
                 remotePort: int = 9190
                 ) -> None:
        super().__init__()
        
        self.sockProxyAddr = sockProxyAddr
        self.sockProxyPort = sockProxyPort
        self.remoteAddr = remoteAddr
        self.remotePort = remotePort
        super().__init__()
        # self.run()
    
    def run(self):
        try:
            asyncio.run(self.startSockServer())
        except KeyboardInterrupt:
            return
    
    async def startSockServer(self) -> None:
        """启动Socks5服务器"""
        # TODO: 给Socks连接也加上TLS加密
        
        server = await asyncio.start_server(
            self.localSockHandle, self.sockProxyAddr, self.sockProxyPort,
            backlog=4096)

        addr = server.sockets[0].getsockname()
        self.logger.warning(f'服务器启动, 端口:{addr[1]}')

        async with server:
            await server.serve_forever()
            
    
    @StreamBase.handlerDeco
    async def localSockHandle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """处理本地Socks5代理的请求"""
        # TODO: 和本地的连接异常断开后会导致大量的内存泄露，需要验证
        
        
        requestId = self.totalConnections - 1
        logger = self.logger.get_child(str(requestId))
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
            if not (2 in set(methods)):
                raise SocksError('不支持的身份验证方式')

            # 发送支持的methods
            writer.write(pack('!BB', SOCKS_VERSION, 2))  # 2表示用户名密码方式
            await writer.drain()

            # 验证身份信息
            # [文档](https://www.jianshu.com/p/8001c40e5f83)
            version = ord(await reader.readexactly(1))
            assert version == 1, SocksError('不支持的身份验证版本')

            usernameLen = ord(await reader.readexactly(1))
            username = (await reader.readexactly(usernameLen)).decode('utf-8')

            passwordLen = ord(await reader.readexactly(1))
            password = (await reader.readexactly(passwordLen)).decode('utf-8')

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
            version, cmd, _, addressType = unpack("!BBBB", await reader.readexactly(4))
            assert version == SOCKS_VERSION, SocksError('不支持的Socks版本')
          
            if addressType == 1:  # IPv4
                trueDomain = ''
                trueIpBytes = await reader.readexactly(4)
                trueIp = socket.inet_ntoa(trueIpBytes)
                pass
            elif addressType == 3:  # 域名
                trueIp = ''
                domainLength = (await reader.readexactly(1))[0]  # 返回int类型
                trueDomainBytes = await reader.readexactly(domainLength)
                trueDomain = trueDomainBytes.decode('utf-8')
                pass
            else:
                raise SocksError(f'不支持的地址类型{addressType}')

            truePort = unpack('!H', await reader.readexactly(2))[0]
            logger.info(f'客户端请求 > {trueIp}|{trueDomain}:{truePort}')
            
            # 在远程创建真实链接
            remoteClient = Client(self.remoteAddr, self.remotePort, tag=requestId)
            response = await remoteClient.remoteHandshake(payload={
                'ip': trueIp,
                'domain': trueDomain,
                'port': truePort
            }
            )
            if not response is None:
                bindAddress, bindPort = response
            else:
                raise RemoteClientError('远程服务器返回错误')
            bindAddressBytes = socket.inet_aton(bindAddress)
            bindAddressInt = unpack('!I', bindAddressBytes)[0]
            

            # 对Socks客户端响应连接的结果
            reply = pack("!BBBBIH", SOCKS_VERSION, 0,
                         0, 1, bindAddressInt, bindPort)
            writer.write(reply)
            await writer.drain()

            # 建立数据交换
            if reply[1] == 0 and cmd == 1:
                await remoteClient.exchangeStream(reader, writer, remoteClient.remoteReader, remoteClient.remoteWriter)

            
        except RemoteClientError as e:
            logger.warning(f'远程创建连接失败 > {e}')
            
        except SocksError as e:
            logger.warning(f'Socks错误 > {e}')

        except OSError as e:
            logger.warning(f'OS错误 > {e}')
            
        except Exception as e:
            logger.warning(f'未知错误 > {e}')

            
        finally:
            try:
                writer.close()
                await writer.wait_closed()
                logger.debug(f'本地连接已关闭')
            except Exception as e:
                logger.critical(f'关闭本地连接失败 > {e}')
                
            try:
                await remoteClient.remoteClose()
            except Exception as e:
                logger.debug(f'关闭远程连接失败 > {e}')
                
            """收尾工作"""
            logger.info(f'请求处理结束')
                        
            # DEBUG
            # objgraph.show_growth()
            return


if __name__ == '__main__':
    proxy_server = SockRelay(
        sockProxyAddr='0.0.0.0',
        sockProxyPort=9011,
        # remoteAddr='192.168.3.131',
        remoteAddr='pyxy.s-2.link',
        remotePort=9190)
    proxy_server.run()
    