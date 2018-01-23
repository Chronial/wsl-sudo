Sudo for Cygwin
===============

What is this?
-------------

This tool emulates Unix sudo in cygwin. It allows you to run applications in
elevated user mode from a non-elevated cygwin shell.

It is based on [nu774's tool](https://github.com/nu774/sudo-for-cygwin) and has
full terminal support, so you can run interactive applications like vim or a
shell through it.


Requirements
------------

`cygwin-sudo` requires Python >= 3.5. You can get it by installing `python3`
with the cygwin installer.


How to setup
------------

Clone this repository or just download `cygwin-sudo.py`.

You can test if the script works by running `python3 cygwin-sudo.py id -nG` and
comparing the output with just running `id -nG`. Running the command through
cygwin-sudo should add an Administrator group to the outputed list.

For convenience, you might want to add an alias to this script, eg:

    alias sudo="python3 /path-to-cygwin-sudo/cygwin-sudo.py"


Usage examples:

    $ sudo vim /etc/hosts
    $ sudo cp foo.txt /cygdrive/c/Program Files/
    $ sudo cygstart cmd  # open elevated standard command prompt
    $ sudo cygstart regedit
    $ sudo bash  # open elevated shell

Note that it will open an UAC prompt every time it is run, so if you want to
run multiple commands in succession, you should open an elevated shell (see
example above) and run your commands from there


How it works
------------

When run, `cygwin-sudo` uses `cygstart` to run second process in elevated mode.
This elevated process will then run the given command and connect to the
initial process to exchange input and output.

The given command runs in a pty, so it *acts* as if running in an ordinary
terminals. Therefore you can run cygwin's interactive console-based program
like vim or less.
