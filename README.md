# Zbuilder: Building VMs and applying ansible playbooks


## Install zbuilder

At the moment there is no pip package so you can try:
```
pip3 install --user git+https://github.com/hasiotis/zbuilder
```

## Developer setup:

One way to setup development environment is:

```
git clone git@github.com:hasiotis/zbuilder.git --branch develop
cd zbuilder
pipenv --three
pipenv shell
make init
```

Next time just:

```
cd zbuilder
pipenv shell
```

## Usage

For vagrant provider check [here](docs/Vagrant.md).
For GCP provider check [here](docs/GCP.md).
