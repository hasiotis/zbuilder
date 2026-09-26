Installation
============

Prerequisites
-------------

The libvirt bindings are a hard dependency of zbuilder and compile against the
libvirt headers, so those have to be in place before the install::

 apt install libvirt-dev pkg-config gcc     # or: dnf install libvirt-devel

Install zbuilder
----------------

Install and update using::

 pip3 install --user --upgrade zbuilder

If you wish to not mess with your ansible installation, try::

 pipx install zbuilder

Developer setup
---------------

The project is managed with uv. One way to setup development environment is::

 $ git clone git@github.com:hasiotis/zbuilder.git
 $ cd zbuilder
 $ make init
 $ . .venv/bin/activate

Next time just::

 $ cd zbuilder
 $ uv sync
 $ . .venv/bin/activate
