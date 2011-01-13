===============
sudo for cygwin
===============

What is this?
-------------

Emurates Unix sudo in cygwin.

You can use this like::

$ sudo vim /etc/hosts
$ sudo cp foo.txt /cygdrive/c/Program Files/
$ sudo # just invoke elevated shell

How it works
------------

This is in fact a client/server application.

It looks as if the child process is running in the current terminal.
However, in fact, it's invoked by the server, and running remotely
(though "remote" is in the same PC).

You must launch a python script named **sudoserver.py** beforehand,
in desired privileges. For this purpose, Windows built-in
Task Scheduler is handy.

**sudoserver.py** opens a listening port 127.0.0.1:7070 (by defaults), 
then sits and wait for connections from **sudo**.

**sudo**, when invoked, connects to the **sudoserver**.
Then it sends it's command line arguments, environment variables,
current working directory, and terminal window size, to the **sudoserver**.

When **sudoserver** accepts connection from **sudo**, **sudoserver** forks a child process with pty, set up environments, current working directory or something, then execute the process.

The child process is spawned by the **sudoserver**, therefore it runs in the privileges same as the server.

And, as the child process runs in a pty, it *acts* as if running in ordinary terminals. Therefore you can run cygwin's interactive console-based program like vim or less.

After execution, **sudo** and **sudoserver** bridges user's tty and the process I/O.

Requirement
-----------

Both sudo and sudoserver.py is written in python, therefore you need to install Python.

Also, you need Python module named greenlet, and eventlet. These are not packaged in cygwin, therefore you must manually install them.

How to setup
------------

1. Install python with cygwin installer.

2. Download greenlet. It can be downloaded from "http://pypi.python.org/pypi/greenlet/"

3. Download eventlet. It can be downloaded from "http://pypi.python.org/pypi/eventlet/"

4. Install greenlet package. Extract the archive, and move to the directory. then you type in the cygwin shell::

  $ python setup.py install

5. Install eventlet package. Extract the archive, and do the same with the above instruction for greenlet. 

6. You can place sudo and sudoserver.py where you like. You will want to execute sudo via command line, therefore /usr/local/bin or somewhere in the PATH will be good.

7. If you want to use the TCP portnumber other than 7070 (default value), you have to edit the both script manually. It is written like::

  PORT = 7070

8. At first, probably you want to test it. From cygwin shell, invoke sudoserver.py like::

  $ /path/to/sudoserver.py

9. And then, test sudo command like::

  $ sudo ls -l

10. If it seems to work, you can register sudoserver.py to the Windows task scheduler. I recommend you the following setup.

   - Action: "Start a program"
   - Triggers: "At log on"
   - "Run with highest privileges": checked.
   - "Program/script": C:\\cygwin\\bin\\python.exe
   - "Add arguments(optional)": /path/to/sudoserver.py -nw

With argument "-nw" is specified, sudoserver.py hides it's console window.

11. **sudoserver** sets an aditional environment variables ELEVATED_SHELL=1. You can use this to change your shell prompt (PS1), in order to see which environment you are in.
