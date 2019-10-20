# Zbuilder: Building VMs and applying ansible playbooks


## Install zbuilder

At the moment there is no pip package so you can try:
```
pip3 install --user git+https://github.com/hasiotis/zbuilder
``

## Initial zbuilder setup

Assuming that you have two VM providers, one for development (vagrant)
and one for staging (Digital Ocean), you will have to let zbuilder know
about it.

First setup the development provider:
```
$ zbuilder config provider --type vagrant devel
$ zbuilder config provider --type do staging
```

## Developer setup:

One way to setup development environment is:

``` shell
git clone git@github.com:hasiotis/zbuilder.git --branch develop
cd zbuilder
pipenv --three
pipenv shell
make init
```

Next time just:

``` shell
cd zbuilder
pipenv shell
```
