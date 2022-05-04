from aisle import LOG
import uuid
import json
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# debug
# from pympler import asizeof 
# import sys
# from objprint import op


class Key():
    """用来加解密的key

    Raises:
        TypeError: 如果__set__传入了非bytes类型
        ValueError: 如果__set__传入非16位

    Returns:
        self: 一个16位比特串
    """
    __slots__ = '_keyBytes'
    
    
    def __init__(self, keyString: str='') -> None:
        if not keyString:
            keyString = str(uuid.uuid4().hex)
        self.keyBytes = keyString.encode('utf-8')
        pass
            
    @property
    def keyBytes(self) -> bytes:
        return self._keyBytes

    @keyBytes.setter
    def keyBytes(self, value: bytes):
        if not isinstance(value, bytes):
            raise TypeError('key must be bytes')
        elif len(value) != 32:
            raise ValueError('key must be 32 bytes')
        else:
            self._keyBytes = value
            
    @property
    def keyString(self) -> str:
        return str(self.keyBytes)

    @keyString.setter
    def keyString(self, value: str):
        self.keyBytes = value.encode('utf-8')
            


class Cryptor():
    __slots__ = ['cipher', 'blockSize']
    
    
    def __init__(self, keyBytes: bytes) -> None:
        super().__init__()
        now = time.time()
        self.cipher = AES.new(keyBytes, AES.MODE_ECB)
        self.blockSize = 32

    def encrypt(self, b: bytes) -> bytes:
        """输入的字节串无需填充"""
        return self.cipher.encrypt(pad(b, self.blockSize))

    def decrypt(self, b: bytes) -> bytes:            
        try:
            return unpad(self.cipher.decrypt(b), self.blockSize)
        except ValueError:
            """解密错误，解密失败"""
            raise DecryptError('解密错误')


class Block():
    """安全区块
    """
    __slots__ = 'uuid', 'key', 'payload', 'timestamp', '_crpto'
    
    @classmethod
    def fromBytes(cls, key: Key, b: bytes) -> 'Block':
        """解密字节串并转换为Block对象

        Args:
            key (Key): 加密密钥

        Raises:
            DecryptError: 解密错误，解密失败
        """
        crpto = Cryptor(key.keyBytes)
        rebuildDict = json.loads(crpto.decrypt(b).decode('utf-8'))
        vTime = rebuildDict['timestamp'] - int(time.time())  # 验证时间是否大于10秒
        if vTime >= 10:
            raise DecryptError('时间戳误差大于10秒')
        
        rtn = cls(key, {})  # 创建空的Block对象
        rtn.uuid = rebuildDict['uuid']  # 强制重载
        rtn.payload = rebuildDict['payload']  # 强制重载
        rtn.timestamp = rebuildDict['timestamp']
        
        return rtn

    
    def __init__(self, key: Key, payload: dict = {}) -> None:
        """安全区块构造函数"""
        super().__init__()
        
        # 四个参数（简称ukpt）都会加密
        self.uuid = uuid.uuid4().hex
        self.key = key.keyString
        self.payload = payload
        self.timestamp = int(time.time())
        self._crpto = Cryptor(key.keyBytes)
        pass
    
    @property
    def blockBytes(self) -> bytes:
        """自我加密后，返回ukp的字节串"""
        rtn = self._crpto.encrypt(json.dumps(self.__ukpt).encode('utf-8'))
        return rtn
    
    def __enter__(self) -> 'Block':
        """上下文管理器支持，返回自身"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器支持，减小内存消耗"""
        del self
        
    @property
    def __ukpt(self) -> dict:
        # ukpt取首字母
        return {
            'uuid': self.uuid,
            'key': self.key,
            'payload': self.payload,
            'timestamp': self.timestamp
            
        }

        


class DecryptError(Exception):
    """解密错误"""
    pass


def test():
    key = Key()
    LOG.info(key.keyBytes)
    blk = Block(key, {'a': 1})
    print(blk.blockBytes)
    blk2 = Block.fromBytes(key, blk.blockBytes)
    pass
    
if __name__ == '__main__':
    test()