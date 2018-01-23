#!/usr/bin/env python3
import argparse
import errno
import fcntl
import os
import pty
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import traceback
import tty
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing, contextmanager

import termios

CMD_DATA = 1
CMD_WINSZ = 2


class PartialRead(Exception):
    pass


class ElevatedServer:
    def main(self, argv):
        port = int(argv[1])
        password_file = argv[2]
        with open(password_file, 'rb') as f:
            password = f.read()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with closing(self.sock):
            self.sock.connect(('127.0.0.1', port))
            received_password = self.recv_message()
            if received_password != password:
                print("ERROR: invalid password")
                sys.exit(1)

            child_args = [self.recv_message() for _ in range(4)]
            print("Elevated sudo server running:")
            print("> " + child_args[0].decode())

            child_pid, child_pty = pty.fork()
            if child_pid == 0:
                self.child_process(*child_args)
            else:
                self.child_pid = child_pid
                self.child_pty = child_pty
                self.main_process()

    def main_process(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self.pty_read_loop)
            executor.submit(self.sock_read_loop)

    def child_process(self, cmdline, cwd, winsize, env):
        try:
            self.sock.close()
            os.chdir(cwd)
            fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
            envdict = dict(line.split(b'=', 1) for line in env.split(b'\0'))
            envdict[b'ELEVATED_SHELL'] = b'1'
            argv = cmdline.split(b'\0')
            try:
                os.execvpe(argv[0], argv, envdict)
            except FileNotFoundError:
                print("sudo: Unknown command '{}'".format(os.fsdecode(argv[0])))
        except BaseException:
            traceback.print_exc()
        finally:
            os._exit(1)

    def recv_n(self, n):
        d = []
        while n > 0:
            s = self.sock.recv(n)
            if not s:
                break
            d.append(s)
            n -= len(s)
        if n > 0:
            raise PartialRead('EOF while reading')
        return b''.join(d)

    def recv_message(self):
        length = struct.unpack('I', self.recv_n(4))[0]
        return self.recv_n(length)

    def try_read(self, fd, size):
        try:
            return os.read(fd, size)
        except OSError:
            return b''

    def pty_read_loop(self):
        try:
            for chunk in iter(lambda: self.try_read(self.child_pty, 8192), b''):
                self.sock.sendall(chunk)
            self.sock.shutdown(socket.SHUT_WR)
        except Exception as e:
            traceback.print_exc()

    def sock_read_loop(self):
        try:
            while True:
                message = self.recv_message()
                id, data = struct.unpack('I', message[:4])[0], message[4:]
                if id == CMD_DATA:
                    os.write(self.child_pty, data)
                elif id == CMD_WINSZ:
                    fcntl.ioctl(self.child_pty, termios.TIOCSWINSZ, data)
                    os.kill(self.child_pid, signal.SIGWINCH)
        except PartialRead:
            print('FIN received')
        except Exception:
            traceback.print_exc()


class UnprivilegedClient:
    def main(self, command, window, **kwargs):
        password = os.urandom(32)
        with tempfile.NamedTemporaryFile("wb") as pwf:
            pwf.write(password)
            pwf.flush()
            listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_socket.bind(('127.0.0.1', 0))
            with closing(listen_socket):
                port = listen_socket.getsockname()[1]
                listen_socket.listen(1)

                try:
                    subprocess.check_call([
                        "cygstart", "--action=runas", window,
                        sys.executable, __file__,
                        '--elevated', 'server', str(port), pwf.name])
                except subprocess.CalledProcessError as e:
                    print("Failed to start elevated process")
                    return

                listen_socket.settimeout(5)
                self.sock, acc = listen_socket.accept()

            command_bytes = list(map(os.fsencode, command))
            self.run(password, command_bytes)

    def run(self, password, command):
        with closing(self.sock):
            self.send_message(password)
            self.send_message(b'\0'.join(command))
            self.send_message(os.fsencode(os.getcwd()))
            self.send_message(self.get_winsize())
            self.send_message(b'\0'.join(b'%s=%s' % t for t in os.environb.items()))

            def handle_sigwinch(n, f):
                self.send_command(CMD_WINSZ, self.get_winsize())

            signal.signal(signal.SIGWINCH, handle_sigwinch)

            with self.raw_term_mode():
                fdset = [0, self.sock.fileno()]
                done = False
                while not done:
                    for fd in self.xselect(fdset, (), ())[0]:
                        if fd == 0:
                            self.send_command(CMD_DATA, os.read(0, 8192))
                        else:
                            data = self.sock.recv(8192)
                            if data:
                                os.write(1, data)
                            else:
                                done = True

            self.sock.shutdown(socket.SHUT_WR)

    def xselect(self, *args):
        while True:
            try:
                return select.select(*args)
            except select.error as e:
                if e.args[0] != errno.EINTR:
                    raise

    @contextmanager
    def raw_term_mode(self):
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

    def get_winsize(self):
        if not os.isatty(0):
            return struct.pack('HHHH', 24, 80, 640, 480)

        winsz = struct.pack('HHHH', 0, 0, 0, 0)
        return fcntl.ioctl(0, termios.TIOCGWINSZ, winsz)

    def send_message(self, data):
        length = len(data)
        self.sock.send(struct.pack('I', length))
        self.sock.send(data)

    def send_command(self, cmd, data):
        self.send_message(struct.pack('I', cmd) + data)


def main():
    parser = argparse.ArgumentParser(description="Run a command in elevated user mode")
    window_group = parser.add_mutually_exclusive_group()
    window_group.set_defaults(window='--hide')
    window_group.add_argument('--visible', action='store_const', dest='window',
                              const='--shownormal',
                              help="show the elevated console window")
    window_group.add_argument('--minimized', action='store_const', dest='window',
                              const='--showminnoactive',
                              help="show the elevated console window as a minimized window")
    parser.add_argument('--elevated', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('command', nargs=argparse.PARSER)
    args = parser.parse_args()

    if args.elevated:
        ElevatedServer().main(args.command)
    else:
        UnprivilegedClient().main(**vars(args))


if __name__ == '__main__':
    main()
