# Zbuilder: Building VMs and applying ansible playbooks


## Initial zbuilder setup

Assuming that you have two VM providers, one for development (vagrant)
and one for staging (Digital Ocean), you will have to let zbuilder know
about it.

First setup the development provider:
```
$ zbuilder config provider --type vagrant devel
$ zbuilder config provider --type do staging
```

Developer setup:

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

User setup

``` shell
git clone git@github.com:Workable/zbuilder.git
cd zbuilder
python3 ./setup.py install --user
```
