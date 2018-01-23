#!/usr/bin/env python
import sys
import os
import fcntl
import termios
import tty
import signal
import select
import struct
import socket
import getopt
import errno
import traceback
from contextlib import closing, contextmanager

PORT = 7070

CMD_DATA = 1
CMD_WINSZ = 2


def xselect(*args):
    while True:
        try:
            return select.select(*args)
        except select.error as e:
            if e.args[0] != errno.EINTR:
                raise


def get_winsize():
    if not os.isatty(0):
        return struct.pack('HHHH', 24, 80, 640, 480)

    winsz = struct.pack('HHHH', 0, 0, 0, 0)
    return fcntl.ioctl(0, termios.TIOCGWINSZ, winsz)


@contextmanager
def raw_term_mode():
    if os.isatty(0):
        attr = termios.tcgetattr(0)

        def restore(): return termios.tcsetattr(0, termios.TCSAFLUSH, attr)

        def sighandler(n, f):
            restore()
            sys.exit(2)

        tty.setraw(0)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, sighandler)
    else:
        def restore(): return None

    try:
        yield
    finally:
        restore()


def send_command(fd, data):
    length = len(data)
    fd.send(struct.pack('I', length))
    fd.send(data)


def send_command2(fd, cmd, data):
    send_command(fd, struct.pack('I', cmd) + data)


def main(args):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.connect(('127.0.0.1', PORT))
        send_command(sock, '\0'.join(args))
        send_command(sock, os.getcwd())
        send_command(sock, get_winsize())
        send_command(sock, '\0'.join('%s=%s' % t for t in os.environ.items()))

        def handle_sigwinch(n, f):
            send_command2(sock, CMD_WINSZ, get_winsize())

        with raw_term_mode():
            signal.signal(signal.SIGWINCH, handle_sigwinch)
            fdset = [0, sock.fileno()]
            done = False
            while not done:
                for fd in xselect(fdset, (), ())[0]:
                    if fd == 0:
                        send_command2(sock, CMD_DATA, os.read(0, 8192))
                    else:
                        data = sock.recv(8192)
                        if data:
                            os.write(1, data)
                        else:
                            done = True


if __name__ == '__main__':
    main(sys.argv[1:])
