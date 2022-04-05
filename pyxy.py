from aisle import LOG as logging
from aisle import LogMixin
import select
import socket
import struct
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler

# logging.basicConfig(level=logging.INFO)
SOCKS_VERSION = 5


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass


class SocksProxy(LogMixin, StreamRequestHandler):
    # [资料](https://docs.python.org/zh-cn/3.7/library/socketserver.html)
    username = 'username'
    password = 'password'

    def handle(self):
        # logging.info(self.request)
        self.logger.info('Accepting connection from %s:%s' % self.client_address)

        # greeting header
        # read and unpack 2 bytes from a client
        header = self.connection.recv(2)  # 取数据包的头2字节，作为Socks5协议的版本号和命令类型
        version, nmethods = struct.unpack("!BB", header)

        # [RFC1928](https://www.quarkay.com/code/383/socks5-protocol-rfc-chinese-traslation )
        
        # socks 5
        assert version == SOCKS_VERSION
        assert nmethods > 0

        # get available methods
        methods = self.get_available_methods(nmethods)

        # accept only USERNAME/PASSWORD auth
        if 2 not in set(methods):
            # close connection
            self.server.close_request(self.request)
            return

        # send welcome message
        self.connection.sendall(struct.pack("!BB", SOCKS_VERSION, 2))

        if not self.verify_credentials():
            return

        # request
        version, cmd, _, address_type = struct.unpack("!BBBB", self.connection.recv(4))
        assert version == SOCKS_VERSION

        if address_type == 1:  # IPv4
            ipAddress = socket.inet_ntoa(self.connection.recv(4))
        elif address_type == 3:  # Domain name
            domain_length = self.connection.recv(1)[0]  # 对bytes进行切片[0]，返回一个int，相当于强转
            domainAddress = self.connection.recv(domain_length)
            ipAddress = socket.gethostbyname(domainAddress)  # 将域名解析为IPv4地址  #TODO:需要考虑到DNS也走代理的情况
        
        #TODO: address_type == 4  # IPv6
        
        port = struct.unpack('!H', self.connection.recv(2))[0]  # 对单元素typle切片，返回一个int
        
        
        # reply
        # 创建真实连接
        try:
            if cmd == 1:  # CONNECT
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((ipAddress, port))
                bind_address = remote.getsockname()
            else:
                self.server.close_request(self.request)

            addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
            port = bind_address[1]
            reply = struct.pack("!BBBBIH", SOCKS_VERSION, 0, 0, 1,
                                addr, port)  # 对sock客户端响应连接的结果
            pass
        except Exception as err:
            self.logger.error(err)
            # return connection refused error
            reply = self.generate_failed_reply(address_type, 5)

        self.connection.sendall(reply)

        # establish data exchange、
        # 回传
        if reply[1] == 0 and cmd == 1:
            try:
                self.exchange_loop(self.connection, remote)
            except ConnectionResetError:
                """
                ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。
                应该是数据传回客户端中出现异常
                """
                self.logger.info('客户端关闭了连接')

        self.server.close_request(self.request)

    def get_available_methods(self, n):
        methods = []
        for i in range(n):
            methods.append(ord(self.connection.recv(1)))
        return methods

    def verify_credentials(self):
        # [文档](https://www.jianshu.com/p/8001c40e5f83)
        version = ord(self.connection.recv(1))
        assert version == 1

        username_len = ord(self.connection.recv(1))
        username = self.connection.recv(username_len).decode('utf-8')

        password_len = ord(self.connection.recv(1))
        password = self.connection.recv(password_len).decode('utf-8')

        if username == self.username and password == self.password:
            # success, status = 0
            response = struct.pack("!BB", version, 0)
            self.connection.sendall(response)
            return True

        # failure, status != 0
        response = struct.pack("!BB", version, 0xFF)
        self.connection.sendall(response)
        self.server.close_request(self.request)
        return False

    def generate_failed_reply(self, address_type, error_number):
        return struct.pack("!BBBBIH", SOCKS_VERSION, error_number, 0, address_type, 0, 0)

    def exchange_loop(self, client, remote):

        while True:

            # wait until client or remote is available for read
            r, w, e = select.select([client, remote], [], [])

            if client in r:
                data = client.recv(4096)
                if remote.send(data) <= 0:
                    break

            if remote in r:
                data = remote.recv(4096)
                if client.send(data) <= 0:
                    break


if __name__ == '__main__':
    with ThreadingTCPServer(('127.0.0.1', 9011), SocksProxy) as server:
        server.serve_forever()
