Installation
============

Install zbuilder
----------------

Install and update using::

 pip3 install --user --upgrade zbuilder

If you wish to not mesh with your ansible installation, try::

 pipx install zbuilder

Developer setup
---------------

One way to setup development environment is::

 $ git clone git@github.com:hasiotis/zbuilder.git --branch develop
 $ cd zbuilder
 $ pipenv shell
 $ make init

Next time just::

 $ cd zbuilder
 $ pipenv shell
