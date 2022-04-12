# PyXy

## “朋友需要”

- [PyXy](#pyxy)
  - [“朋友需要”](#朋友需要)
  - [Dependencies](#dependencies)
  - [Before you run](#before-you-run)
    - [Key](#key)
    - [TLS Certificate](#tls-certificate)
  - [Run server and client](#run-server-and-client)
    - [Server side](#server-side)
    - [Client side](#client-side)
  - [Data safety](#data-safety)
  - [Troubleshooting](#troubleshooting)
  - [License](#license)
  - [Develop](#develop)


---

An async stream tunnel program, written in python, using asyncio.

This project is an open-source project, it is absolutely free to use, but you should be aware of the following:
- Do not use it for illegal(in any country or region) purposes.
- Remember there is no warranty for this program, 
- Also no warranty to data , transfer or your privacy safety.


## Dependencies

 **Python 3.7+** is needed, for safety reason and some asyncio future.
 **Pypy** is also welcome. Actually the whole project is tested on pypy.  
 **Python 3.9** is recommended, which is the latest pypy version.  

 In most cases, you can use `pip install -r requirements/compatible.txt` to install all dependencies. If that doesn't work, please open an issue.  
 Using `venv` to creating a virtual environment is also recommended, it's all depended on you.

 If you are using linux system, OR you could make sure that your system could use uvloop module, you can use `pip install -r requirements/with_uvloop.txt` to install all dependencies and uvloop module, which would fasten up the program. You may also install build tools for building uvloop(if error occur when installing uvloop), which could use `sudo apt install build-essential` on Ubuntu to solve.

## Before you run

### Key
There is an AES key using by both client and server. You must create a key file before everything run. A key file must be allocated in this program directory, and named `key`. The key file must be a plain text file, and only contain the key string.  
Key string is a 32-byte string, and it's a hex string.

For example, if you want to use a key string `12345678901234567890123456789012`, you should create a file named `key` in this program directory, and write the following content into it: `12345678901234567890123456789012`  
With no space or newline.

This key file will be used to create a `Key` object in module `SafeBlock`, you could check if you want to.

### TLS Certificate

The best solution is register a domain and apply a SSL certificate.  
In server module, you can set the certificate file and key file in `Server.__init__()` function.  

There are also some other ways to bypass this problem, but it's not recommended.

## Run server and client

### Server side
Running these code on a server with a domain name and a SSL certificate.  
Don't forget to leave the firewall open for this program. The default port is `9190`.  
```bash
python3 server.py
```
These would run the whole server.  

### Client side

```bash
python3 proxy_broker.py
```
These would run the client. Client would opening a sock5 proxy listening on port 9011, if any connection comes, it would connect to server, and then forward the connection.

## Data safety

Data between client and server is encrypted by TLS, using your own SSL certificate.

Data between client and your socks5 proxy is **NOT** encrypted, do not use sock5 proxy on the public!

## Troubleshooting

This project is still in developing, so there are some problems that you may encounter.  
For now troubleshooting is none, but if you have any problem, please open an issue.

## License

GPLv3

## Develop

Git Branch: Dev
Linter: mypy
System: Linux, for testing uvloop and other module purpose  
Python interpreter: Python 3.9.12, using pypy for better performance and gently exiting.
