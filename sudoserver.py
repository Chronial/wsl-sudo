#!/usr/bin/env python
import sys
import os
import fcntl
import termios
import pty
import signal
import select
import struct
import traceback
import eventlet
import socket
import errno

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
    return ''.join(d)

def read_command(sock):
    length = struct.unpack('I', readn(sock, 4))[0]
    return readn(sock, length)

def child(cmdline, cwd, winsize, env):
    try:
        os.chdir(cwd)
        fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
        envdict = dict(line.split('=', 1) for line in env.split('\0'))
        envdict['ELEVATED_SHELL'] = '1'
        if not cmdline:
            shell = envdict.get('SHELL', '/bin/bash')
            os.execvpe(shell, (shell, '-i'), envdict)
        else:
            argv = cmdline.split('\0')
            os.execvpe(argv[0], argv, envdict)
    except:
        traceback.print_exc()
    finally:
        sys.exit(0)

def try_read(fd, size):
    try:
        return os.read(fd, size)
    except:
        return ''

def pty_read_loop(master, sock):
    try:
        for chunk in iter(lambda: try_read(master, 8192), ''):
            sock.sendall(chunk)
        sock.shutdown(socket.SHUT_WR)
    except Exception as e:
        traceback.print_exc()

def sock_read_loop(sock, master, pid):
    try:
        while True:
            command = read_command(sock)
            id, data = struct.unpack('I', command[:4])[0], command[4:]
            if id == CMD_DATA:
                os.write(master, data)
            elif id == CMD_WINSZ:
                fcntl.ioctl(master, termios.TIOCSWINSZ, data)
                os.kill(pid, signal.SIGWINCH)
    except Exception as e:
        if isinstance(e, PartialRead):
            print 'FIN received'
        else:
            traceback.print_exc()

def request_handler(conn, server):
    try:
        child_args = [ read_command(conn) for _ in range(4) ]

        pid, master = pty.fork()
        if pid == 0:
            conn.close()
            server.close()
            child(*child_args)

        with os.fdopen(master, 'r+') as masterfile:
            pool = eventlet.GreenPool()
            pool.spawn_n(pty_read_loop, master, conn)
            pool.spawn_n(sock_read_loop, conn, master, pid)
            pool.waitall()
    except Exception as ex:
        traceback.print_exc()
    finally:
        print 'Closing connection'
        conn.close()

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
    eventlet.patcher.monkey_patch(all=True)
    server = eventlet.listen(('127.0.0.1', PORT))
    signal.signal(signal.SIGCHLD, handle_sigchild)
    while True:
        conn, acc = server.accept()
        print 'Accepted connection from %r' % (acc,)
        eventlet.spawn_n(request_handler, conn, server)

def cygwin_hide_console_window():
    import ctypes
    hwnd = ctypes.cdll.LoadLibrary('kernel32.dll').GetConsoleWindow()
    ctypes.cdll.LoadLibrary('user32.dll').ShowWindow(hwnd, 0)

if __name__ == '__main__':
    if sys.platform == 'cygwin' and len(sys.argv) > 1 and sys.argv[1] == '-nw':
        cygwin_hide_console_window()
    main()
