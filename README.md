# Zbuilder: Building VMs and applying ansible playbooks

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
