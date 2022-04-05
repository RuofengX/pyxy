from multiprocessing.sharedctypes import Value
import grpc
import select
import socket
import struct
import protos.transit_pb2_grpc as transit_pb2_grpc
import protos.transit_pb2 as transit_pb2
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler
from aisle import LogMixin, LOG


class RemoteManager(LogMixin, transit_pb2_grpc.SocketManagerServicer):
    def __init__(self, channel:grpc.Channel):
        self.client = transit_pb2_grpc.SocketManagerStub(channel)
        self.connectPool = []
        super().__init__()
        
        
    def new(self, port:int, ip:int, domain:str):
        if (ip is None) and (domain is None):
            self.logger.error("必须指定IP或域名")
            raise ValueError("You must specify either an ip or a domain")
        response = self.client.new(transit_pb2.SocketReq(port=port, ip=ip, domain=domain))
        socketId, bindAddr, bindPort = response.socketId, response.addr, response.port
        if socketId == 0:
            self.logger.error(f'远程拒绝创建连接')
            return 0
        else:
            self.connectPool.append(socketId)
            return socketId, bindAddr, bindPort
    
    
        
    def close(self, socketId:int):
        if not socketId in self.connectPool:
            self.logger.warning("Socket %d not in local pool", socketId)
        
        return self.client.close(transit_pb2.SocketReq(socketId=socketId)).socketId
            
    def closeAll(self):
        for socketId in self.connectPool:
            self.close(socketId)

    def send(self, socketId: int, localSocket: socket):
        self.client.send(self.__sendItor(socketId, localSocket))
        return localSocket
    
    def __sendItor(self, socketId: int, localSocket: socket):
        while 1:
            data: bytes = localSocket.recv(1522)
            self.logger.info('传输字节')
            self.logger.info(data)
            if not data:
                self.logger.info('关闭传输')
                break
            yield transit_pb2.SendReq(socketId=socketId, data=data)
        

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass
        
class SockParser(LogMixin, StreamRequestHandler):
    """代理请求处理器
    
    处理一次完整的Socks5请求
    """
    SOCKS_VERSION = 5
    username = 'username'
    password = 'password'
    remoteManager = RemoteManager(grpc.insecure_channel('localhost:50051'))
    
        
    def handle(self) -> None:
        # logging.info(self.request)
        self.logger.info('Accepting connection from %s:%s' % self.client_address)

        # greeting header
        # read and unpack 2 bytes from a client
        header = self.connection.recv(2)  # 取数据包的头2字节，作为Socks5协议的版本号和命令类型
        version, nmethods = struct.unpack("!BB", header)

        # [RFC1928](https://www.quarkay.com/code/383/socks5-protocol-rfc-chinese-traslation )
        
        # socks 5
        assert version == self.SOCKS_VERSION
        assert nmethods > 0

        # get available methods
        methods = self.get_available_methods(nmethods)

        # accept only USERNAME/PASSWORD auth
        if 2 not in set(methods):
            # close connection
            self.server.close_request(self.request)
            return

        # send welcome message
        self.connection.sendall(struct.pack("!BB", self.SOCKS_VERSION, 2))

        if not self.verify_credentials():
            return

        # request
        version, cmd, _, address_type = struct.unpack("!BBBB", self.connection.recv(4))
        assert version == self.SOCKS_VERSION
        
        if address_type == 1:  # IPv4
            domainAddress = None
            ipAddress = socket.inet_ntoa(self.connection.recv(4))
        elif address_type == 3:  # Domain name
            ipAddress = None
            domain_length = self.connection.recv(1)[0]  # 对bytes进行切片[0]，返回一个int，相当于强转
            domainAddress = self.connection.recv(domain_length)
            # ipAddress = socket.gethostbyname(domainAddress)  # 将域名解析为IPv4地址  #TODO:需要考虑到DNS也走代理的情况
        
        #TODO: address_type == 4  # IPv6
        
        port = struct.unpack('!H', self.connection.recv(2))[0]  # 对单元素typle切片，返回一个int
        
        
        # reply
        # 创建真实连接
        try:
            if cmd == 1:  # CONNECT
                # remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # remote.connect((ipAddress, port))
                # bind_address = remote.getsockname()
                socketId, bindAddr, bindPort = self.remoteManager.new(port, ipAddress, domainAddress)  # 在远程新建一个链接
            else:
                self.server.close_request(self.request)

            reply = struct.pack("!BBBBIH", self.SOCKS_VERSION, 0, 0, 1,
                                bindAddr, bindPort)  # 对sock客户端响应连接的结果

        except Exception as err:
            self.logger.error(err)
            # return connection refused error
            self.remoteManager.close(socketId)
            reply = self.generate_failed_reply(address_type, 5)

        self.connection.sendall(reply)

        # establish data exchange
        # 回传
        if reply[1] == 0 and cmd == 1:
            try:
                self.exchange_loop(socketId)
            except ConnectionResetError:
                """
                ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。
                应该是数据传回客户端中出现异常
                """
                self.logger.info('客户端关闭了连接')
                self.remoteManager.close(socketId)
        
        # 关闭所有连接
        self.remoteManager.close(socketId)
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
        return struct.pack("!BBBBIH", self.SOCKS_VERSION, error_number, 0, address_type, 0, 0)

    def exchange_loop(self, socketId: int):


            # wait until client or remote is available for read
            # r, w, e = select.select([self.connection], [], [])

            # if client in r:
            #     data = client.recv(4096)
            #     if remote.send(data) <= 0:
            #         break

            # if remote in r:
            #     data = remote.recv(4096)
            #     if client.send(data) <= 0:
            #         break
        self.remoteManager.send(socketId, self.connection)


def test_one():
    channel = grpc.insecure_channel('localhost:50051')
    manager = RemoteManager(channel)
    # sid = manager.new(port=443, ip=None, domain="www.baidu.com")
    # LOG.warning(f'返回 > {sid}')
    try:    
        LOG.info(f'创建')
        socketId, addr, port = manager.new(port=443, ip=None, domain="www.baidu.com")
        LOG.info(f'ID > {socketId} | 地址 > {addr} | 端口 > {port}')
    
    finally:
        LOG.info(f'关闭')
        manager.closeAll()

def test_two():
     with ThreadingTCPServer(('127.0.0.1', 9011), SockParser)as server:
        server.serve_forever()
        
if __name__ == '__main__':
    # for i in range(60000):
    #     test_one()
    test_two()
    
    
    
        
        
