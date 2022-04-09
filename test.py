from aisle import LOG as logging
from objprint import op

def debug():
    
    import ssl 
    from python_socks.sync import Proxy

    proxy = Proxy.from_url('socks5://username:password@127.0.0.1:9011')

    # `connect` returns standard Python socket in blocking mode
    sock = proxy.connect(dest_host='check-host.net', dest_port=443)

    sock = ssl.create_default_context().wrap_socket(
        sock=sock,
        server_hostname='check-host.net'
    )

    request = (
        b'GET /ip HTTP/1.1\r\n'
        b'Host: check-host.net\r\n'
        b'Connection: close\r\n\r\n'
    )
    sock.sendall(request)
    response = sock.recv(4096)
    print(response)

def speedtest():
    import speedtest

    servers = []
    # If you want to test against a specific server
    # servers = [1234]

    threads = None
    # If you want to use a single threaded test
    # threads = 1

    s = speedtest.Speedtest()
    s.get_servers(servers)
    s.get_best_server()
    s.download(threads=threads)
    s.upload(threads=threads)
    s.results.share()

    results_dict = s.results.dict()
    op(results_dict)
    
if __name__ == '__main__':
    # debug()
    # speedtest()
    
    