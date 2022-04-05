from multiprocessing.sharedctypes import Value
import socket
import grpc
import struct
import protos.transit_pb2_grpc as transit_pb2_grpc
import protos.transit_pb2 as transit_pb2
import threading
import random
from concurrent import futures
from aisle import LogMixin, LOG

class SocketPool(LogMixin):
    __maxId = 9999  # 最大连接数
    def __init__(self) -> None:
        self.pool = {}  # 连接容器
        self.poolLock = threading.RLock()  # 连接锁
        
        self.__idSeek = 1  # 记录当前socketId位置，从1开始，0表示错误的连接
        self.__idSeekLock = threading.RLock()  # socketId锁
        
        super().__init__()
        
    def new(self, port: int, ip: int=None, domain:str=None) -> int:
        """新建一个socket

        Args:
            port (int): 端口
            ip (int, optional): IP地址. Defaults to None.
            domain (str, optional): 域名. Defaults to None.

        Raises:
            Exception: IP和域名不能同时为空

        Returns:
            int: socketId标识
        """
        if (ip is None) and (domain is None):
            raise ValueError("必须指定IP或域名")
        
        socketId = self.__uniqueId()
        self.pool[socketId] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.info(f'创建socket > {socketId}')
        
        if domain:
            ip = socket.gethostbyname(domain)
            self.logger.info(f'DNS解析 > {domain} > {ip}')
        
        assert ip
        assert port
        
        # 尝试连接是否成功
        try:
            s = self.pool[socketId]
            # s.bind((socket.gethostbyname(socket.gethostname()), port))
            # 自动bind
            
            s.connect((ip, port))
            bindAddress, bindPort = s.getsockname()
            self.logger.info(f'连接可用 > {socketId} > {bindAddress}:{bindPort}')
            
            # 格式化bindAddress
            bindAddress = struct.unpack("!I", socket.inet_aton(bindAddress))[0]
            
            return socketId, bindAddress, bindPort
        except Exception as e:
            self.logger.warning(f'连接失败 > {e}')
            self.close(socketId)
            return 0, 0, 0
        
        
    def read(self, socketId: int):
        """读取连接的数据流

        Args:
            socketId (int): socketId标识

        Returns:
            str: 读取的数据
        """
        sock = self.pool[socketId]
        while 1:
            try:
                rtn = sock.recv(4096)
                if rtn:
                    yield rtn
                else:
                    return
            except IndexError:
                self.logger.warning(f'socketId索引不存在 > {socketId}')
                return None
            
            except IOError as e:
                self.logger.error(f'读取数据失败 > {socketId}')
                raise e
    
    def write(self, socketId: int, msg: bytes):
        """向套接字写入字节

        Args:
            msg (bytes): 需要写入的字节
        """
        if msg:
            try:
                connect = self.pool[socketId]
            except IndexError:
                self.logger.warning(f'socketId索引不存在 > {socketId}')
                return
            
            try:
                connect.send(msg)
            except Exception as e:
                raise e
        else:
            return
        
    def close(self, socketId: int):
        """关闭连接

        Args:
            socketId (int): socketId标识

        Returns:
            int: socketId表示，若为0则表示没有这个连接
        """
        try:
            self.pool[socketId].close()
            del self.pool[socketId]
            self.logger.info(f'关闭连接 > {socketId}')
            return socketId
        except IndexError:
            self.logger.warning(f'socketId索引不存在 > {socketId}')
            return 0
    
    def __uniqueId(self) -> int:
        """线程安全地获取正确的socketId

        Returns:
            int: socketId标识
        """
        self.__idSeekLock.acquire()
        if self.__idSeek <= self.__maxId:
            rtn = self.__idSeek
            self.__idSeek += 1
        else:
            self.__idSeek = 1
            rtn = self.__idSeek
        
        self.__idSeekLock.release()
        return rtn
            
    
class SocketManagerServicer(LogMixin, transit_pb2_grpc.SocketManagerServicer):
    
    def __init__(self):
        self.socketPool = SocketPool()
        super().__init__()
        
    def new(self, request, context):
        if request.ip:
            self.logger.info(f'远程尝试建立连接 | 地址 > {request.ip}:{request.port}')
        if request.domain:
            self.logger.info(f'远程尝试建立连接 | 地址 > {request.domain}:{request.port}')
            
        try:
            socketId, addr, port= self.socketPool.new(
                request.port, 
                request.ip, 
                request.domain
            )
            return transit_pb2.SocketResp(
                socketId=socketId,
                addr = addr,
                port = port
                )
        except ValueError:
            self.logger.warning("远程发送的数值错误")
            return transit_pb2.SocketResp(socketId=0)
    
    def send(self, request_iterator, context):
        for request in request_iterator:
            
            socketId = request.socketId
            self.logger.info(f'远程尝试发送数据 | socketId > {request.socketId}')
            self.logger.info(f'远程尝试发送数据 | data > {request.data}')
            self.socketPool.write(request.socketId, request.data)
        return transit_pb2.SendResp(socketId=socketId)
            
    def read(self, request, context):
        self.logger.info(f'远程尝试读取数据 | socketId > {request.socketId}')
        
        transit_pb2.ReadResp()#TODO:
    
    def close(self, request, context):
        self.logger.info(f'远程尝试关闭连接 | 地址 > {request.socketId}')
        rtn = self.socketPool.close(request.socketId)
            
        return transit_pb2.SocketResp(socketId=rtn) 

    def __readItor(self, socketId: int):
        while 1:
            data: bytes = self.socketPool.read().recv(1522)
            self.logger.info(f'读取数据 | socketId > {socketId}')
            self.logger.info(f'读取数据 | data > {data}')
            if not data:
                self.logger.info(f'关闭连接 | socketId > {socketId}')
                self.socketPool.close(socketId)
            yield transit_pb2.SocketResp(data=data)
        
        
        
if __name__ == '__main__':
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    transit_pb2_grpc.add_SocketManagerServicer_to_server(SocketManagerServicer(), server)
    server.add_insecure_port('localhost:50051')
    LOG.info('服务开始，端口：50051')
    server.start()
    server.wait_for_termination()
    
    