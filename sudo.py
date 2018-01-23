#!/usr/bin/env python3
import errno
import fcntl
import os
import select
import signal
import socket
import struct
import subprocess
import tempfile
import sys
import tty
from contextlib import ExitStack, closing, contextmanager

import termios

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
    if not os.isatty(0):
        yield
    else:
        with ExitStack() as stack:
            attr = termios.tcgetattr(0)
            stack.callback(termios.tcsetattr, 0, termios.TCSAFLUSH, attr)

            def sighandler(n, f):
                stack.close()
                sys.exit(2)

            tty.setraw(0)
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, sighandler)

            yield


def send_message(fd, data):
    length = len(data)
    fd.send(struct.pack('I', length))
    fd.send(data)


def send_command(fd, cmd, data):
    send_message(fd, struct.pack('I', cmd) + data)


def client_main(password, args):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.connect(('127.0.0.1', PORT))
        send_message(sock, password)
        send_message(sock, b'\0'.join(args))
        send_message(sock, os.fsencode(os.getcwd()))
        send_message(sock, get_winsize())
        send_message(sock, b'\0'.join(b'%s=%s' % t for t in os.environb.items()))

        def handle_sigwinch(n, f):
            send_command(sock, CMD_WINSZ, get_winsize())

        signal.signal(signal.SIGWINCH, handle_sigwinch)

        with raw_term_mode():
            fdset = [0, sock.fileno()]
            done = False
            while not done:
                for fd in xselect(fdset, (), ())[0]:
                    if fd == 0:
                        send_command(sock, CMD_DATA, os.read(0, 8192))
                    else:
                        data = sock.recv(8192)
                        if data:
                            os.write(1, data)
                        else:
                            done = True


def main():
    password = os.urandom(32)
    sudoserver = os.path.dirname(os.path.abspath(__file__)) + '/sudoserver.py'
    with tempfile.NamedTemporaryFile("wb") as tf:
        tf.write(password)
        tf.flush()
        subprocess.run(["cygstart", "--action=runas", "--minimize",
                        sys.executable, sudoserver, tf.name])

        argvb = list(map(os.fsencode, sys.argv))
        client_main(password, argvb[1:])


if __name__ == '__main__':
    main()
