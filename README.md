# PyXy

## “朋友需要”

- [PyXy](#pyxy)
  - [“朋友需要”](#朋友需要)
  - [Dependencies](#dependencies)
    - [Known issues](#known-issues)
  - [Before you run](#before-you-run)
    - [TLS Certificate](#tls-certificate)
  - [Run server and client](#run-server-and-client)
    - [Server side](#server-side)
    - [Client side](#client-side)
  - [Data safety](#data-safety)
  - [Troubleshooting](#troubleshooting)
  - [License](#license)
  - [Development Guide](#development-guide)


---

An async stream tunnel program, written in python, using asyncio.

This project is an open-source project, it is absolutely free to use, but you should be aware of the following:
- Do not use it for illegal(in any country or region) purposes.
- Remember there is no warranty for this program, 
- Also no warranty to data , transfer or your privacy safety.


## Dependencies

**CPython 3.7+** is needed for safety reason and some asyncio future.  
**Pypy** is NOT welcome here since it's lack of support for uvloop. You can check these issues here:

- https://github.com/PyO3/pyo3/issues/2137
- https://github.com/MagicStack/uvloop/issues/380

In most cases, you can use `pip install -r requirements/compatible.txt` to install all dependencies. If that doesn't work, please open an issue.  
Using `venv` to creating a virtual environment is also recommended, it's all depended on you.

If you are using linux system, OR you could make sure that your system could use uvloop module, I **strongly** recommend you to use `pip install -r requirements/with_uvloop.txt` to install all dependencies and uvloop module, which would fasten up the program. You may also install build tools for building uvloop(if error occur when installing uvloop), which could use `sudo apt install build-essential` on Ubuntu to solve.  
Uvloop will boost the program into a higher level, if you are running on weak ARM or little VPS server, MAKE SURE you are install uvloop, and the module is imported correctly.

Tested environment is `CPython3.8.10` with `uvloop` module.

### Known issues

> Use pip to install psutil may fail on some linux system. You could try to use `sudo apt install gcc python3-dev` on Debian-based distro to install the dependence to fix.  
> https://github.com/giampaolo/psutil/issues/1142

## Before you run

### TLS Certificate

The best solution is register a domain and apply a SSL certificate.  
In server module, you can set the certificate file and key file in `Server.__init__()` function.  

There are also some other ways to bypass this problem, but it's not recommended.

## Run server and client

At first time you run `python3 server.py` or `python3 proxy_broker.py`, the program will go into error. But don't worry, you just need to change the generated config file `config.toml`. Set everything in it correctly according to `config.example`. You should also make sure that the config on server and local are same. And, that's it!

### Server side
Running these code on a server with a domain name and a SSL certificate, which is configured in config.toml file.  
Don't forget to leave the firewall open for this program. The default port is `9190`.  

```bash
python3 server.py
```

These would run the whole server.  

### Client side

Copy the config file from server, and then run:  

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

## Development Guide

If you want to get involved in, just fork this repo, and create a feature branch. Issue or PR is welcome here!  
