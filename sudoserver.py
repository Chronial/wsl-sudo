#!/usr/bin/env python3
import errno
import fcntl
import os
import pty
import signal
import socket
import struct
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import termios

PORT = 7070
CMD_DATA = 1
CMD_WINSZ = 2


class PartialRead(Exception):
    pass


def readn(sock, n):
    d = []
    while n > 0:
        s = sock.recv(n)
        if not s:
            break
        d.append(s)
        n -= len(s)
    if n > 0:
        raise PartialRead('EOF while reading')
    return b''.join(d)


def read_command(sock):
    length = struct.unpack('I', readn(sock, 4))[0]
    return readn(sock, length)


def child(cmdline, cwd, winsize, env):
    os.chdir(cwd)
    fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
    envdict = dict(line.split(b'=', 1) for line in env.split(b'\0'))
    envdict[b'ELEVATED_SHELL'] = b'1'
    if not cmdline:
        shell = envdict.get(b'SHELL', b'/bin/bash')
        os.execvpe(shell, (shell, '-i'), envdict)
    else:
        argv = cmdline.split(b'\0')
        os.execvpe(argv[0], argv, envdict)


def try_read(fd, size):
    try:
        return os.read(fd, size)
    except Exception:
        return b''


def pty_read_loop(child_pty, sock):
    try:
        for chunk in iter(lambda: try_read(child_pty, 8192), b''):
            sock.sendall(chunk)
        sock.shutdown(socket.SHUT_WR)
    except Exception as e:
        traceback.print_exc()


def sock_read_loop(sock, child_pty, pid):
    try:
        while True:
            command = read_command(sock)
            id, data = struct.unpack('I', command[:4])[0], command[4:]
            if id == CMD_DATA:
                os.write(child_pty, data)
            elif id == CMD_WINSZ:
                fcntl.ioctl(child_pty, termios.TIOCSWINSZ, data)
                os.kill(pid, signal.SIGWINCH)
    except Exception as e:
        if isinstance(e, PartialRead):
            print('FIN received')
        else:
            traceback.print_exc()


def request_handler(conn):
    with closing(conn):
        child_args = [read_command(conn) for _ in range(4)]
        print("Running command: " + child_args[0].decode())
        if child_args[0] == "su_exit":
            sys.exit()

        child_pid, child_pty = pty.fork()
        if child_pid == 0:
            conn.close()
            try:
                child(*child_args)
            except BaseException:
                traceback.print_exc()
            finally:
                sys.exit(0)
        else:
            with ThreadPoolExecutor(max_workers=2) as executor:
                executor.submit(pty_read_loop, child_pty, conn)
                executor.submit(sock_read_loop, conn, child_pty, child_pid)


def handle_sigchild(n, f):
    while True:
        try:
            if os.waitpid(-1, os.WNOHANG) == (0, 0):
                break
        except OSError as e:
            if e.errno != errno.ECHILD:
                traceback.print_exc()
            break


def main():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind(('127.0.0.1', PORT))
    signal.signal(signal.SIGCHLD, handle_sigchild)
    with closing(serversocket):
        serversocket.listen()
        conn, acc = serversocket.accept()
        print('Accepted connection from %r' % (acc,))
    with closing(conn):
        request_handler(conn)


def cygwin_hide_console_window():
    import ctypes
    hwnd = ctypes.cdll.LoadLibrary('kernel32.dll').GetConsoleWindow()
    ctypes.cdll.LoadLibrary('user32.dll').ShowWindow(hwnd, 0)


if __name__ == '__main__':
    if sys.platform == 'cygwin' and len(sys.argv) > 1 and sys.argv[1] == '-nw':
        cygwin_hide_console_window()
    main()
