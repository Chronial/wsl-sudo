Sudo for WSL
===============

What is this?
-------------

This tool allows you to run applications in windows elevated user mode from a
non-elevated wsl shell.

It  has full terminal support, so you can run interactive applications like vim
or a shell through it.


Requirements
------------

`wsl-sudo` requires Python >= 3.5. It should be preinstalled on any modern
linux distribution.


How to setup
------------

Clone this repository or just download `wsl-sudo.py`.

You can test if the script works by running `python3 wsl-sudo.py net.exe sessions`
and comparing the output with just running `net.exe sessions`.

For convenience, you might want to add an alias to this script, eg:

    alias wudo="python3 /path-to-wsl-sudo/wsl-sudo.py"


Usage examples
--------------

    $ wudo vim /mnt/c/Windows/System32/Drivers/etc/hosts
    $ wudo cp foo.txt /mnt/c/Program Files/
    $ wudo cmd  # open elevated standard command prompt
    $ wudo bash  # open elevated shell
    $ wudo regedit

Note that it will open an UAC prompt every time it is run, so if you want to
run multiple commands in succession, you should open an elevated shell (see
example above) and run your commands from there


How it works
------------

When run, `wsl-sudo` uses `powershell` to run a second process in elevated mode.
For security reasons, Windows prevents most kinds of communication between
elevated and non-elevated processes. So, the elevated process connects to the
non-elevated process via TCP for communication. To prevent other processes from
interfering with this connection, it's secured with a random password.

The elevated process will then run the given command and exchange input and 
output with the original process via the TCP connection. The command
is run in a pty, so it *acts* as if running in an ordinary terminal.
Therefore, you can run interactive console-based programs like vim or less.


Related Projects
----------------
* [nu774's sudo-for-cygwin](https://github.com/nu774/sudo-for-cygwin): The inspiration for this tool
* [cygwin-sudo](https://github.com/Chronial/cygwin-sudo): A cygwin version of this tool
