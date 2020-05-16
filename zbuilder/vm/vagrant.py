import click
import shutil
import jinja2

from zbuilder.helpers import runCmd

VAGRANT_FILE = '''
VAGRANTFILE_API_VERSION = "2"
VBOX_ROOT = `VBoxManage list systemproperties | grep "Default machine folder:"`.split(%r{:\s+})[1].chomp

class VagrantPlugins::ProviderVirtualBox::Action::Network
  def dhcp_server_matches_config?(dhcp_server, config)
    true
  end
end

publickey = File.read(File.expand_path('{{ pubkey }}'))

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.ignore_private_ip = true
  config.hostmanager.include_offline = true
  config.ssh.insert_key = false
  config.ssh.private_key_path = ["{{ privkey }}", "~/.vagrant.d/insecure_private_key"]

  zservers = {
{% for h, p in hosts.items() %}
    :'{{ h }}' {{ ' ' * (20 - h|string|count) }}  => { memory: {{ p['memory'] }}, vcpus: {{ p['vcpus'] }}, box: '{{ p['box'] }}', aliases: '{{ p['aliases'] }}', disks: '{{ p['disks'] }}', nics: {{ p['nics']|default(1) }} },
{% endfor %}
  }

  zservers.each do |zname, zparam|
    config.vm.define zname do |srvcfg|
      srvcfg.vm.box = zparam[:box]
      for i in 1..zparam[:nics]
        srvcfg.vm.network :private_network, type: "dhcp"
      end
      srvcfg.vm.host_name = zname.to_s
      srvcfg.vm.provision "file", source: "{{ pubkey }}", destination: ".ssh/authorized_keys"
      domain = zname.to_s.sub(/^.*?\./, "")
      srvcfg.hostmanager.aliases = zparam[:aliases].split(" ").map{|x| [x + '.' + domain] }
      srvcfg.vm.provider "virtualbox" do |v|
        v.name = zname.to_s
        v.memory = zparam[:memory]
        v.cpus = zparam[:vcpus]
        v.customize ["modifyvm", :id, "--vram", "16"]
        v.customize ["modifyvm", :id, "--vrde", "off"]
        v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
        v.customize ["modifyvm", :id, "--nictype1", "virtio"]
        v.customize ["modifyvm", :id, "--nictype2", "virtio"]
        v.customize ["modifyvm", :id, "--natdnsproxy1", "on"]
        zparam[:disks].split(",").map { |s| s.to_i }.each_with_index do |size, i|
            disk_fname = File.join(VBOX_ROOT, zname.to_s, "disk#{i+2}_#{zname}.vmdk")
            unless File.exist?(disk_fname)
                v.customize ['createhd', '--filename', disk_fname, '--size', size * 1024, '--format', 'VMDK']
            end
            v.customize [
                'storageattach', :id,
                '--storagectl', 'SATA Controller',
                '--port', i+1,
                '--device', 0,
                '--type', 'hdd',
                '--medium', disk_fname
            ]
        end
      end

      srvcfg.hostmanager.ip_resolver = proc do |vm, resolving_vm|
        if vm.id
            ret = 'NOT FOUND'
            loop do
                ret = `VBoxManage guestproperty get #{vm.id} "/VirtualBox/GuestInfo/Net/1/V4/IP"`.split()[1]
                break if ret != 'value'
            end
            ret
        end
      end

    end
  end
end
'''


class vmProvider(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def _cmd(self, hosts, cmd):
        self.setVagrantfile(pubkey=self.cfg['state'].vars["ZBUILDER_PUBKEY"], hosts=hosts)
        for h in hosts:
            if hosts[h]['enabled']:
                click.echo("  - Host: {}".format(h))
                runCmd(cmd.format(host=h), verbose=self.cfg['state'].verbose)

    def build(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')

    def up(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')

    def halt(self, hosts):
        self._cmd(hosts, 'vagrant halt {host}')

    def destroy(self, hosts):
        self._cmd(hosts, 'vagrant destroy --force {host}')

    def dnsupdate(self, hosts):
        self._cmd(hosts, 'vagrant hostmanager {host}')

    def snapCreate(self, hosts):
        self._cmd(hosts, 'vagrant snapshot save {host} zbuilder --force')

    def snapRestore(self, hosts):
        click.echo("  Halting")
        self._cmd(hosts, 'vagrant halt {host}')
        click.echo("  Restoring")
        self._cmd(hosts, 'vboxmanage snapshot {host} restore zbuilder')
        click.echo("  Booting up")
        self._cmd(hosts, 'vboxmanage startvm {host} --type headless')

    def snapDelete(self, hosts):
        self._cmd(hosts, 'vagrant snapshot delete {host} zbuilder')

    def params(self, params):
        if 'disks' in params.keys():
            return {k: params[k] for k in ['box', 'vcpus', 'memory', 'disks']}
        else:
            return {k: params[k] for k in ['box', 'vcpus', 'memory']}

    def config(self):
        return shutil.which("vagrant")

    def status(self):
        if shutil.which("vagrant"):
            return 'PASS'
        else:
            return 'Vagrant binary not found'

    def setVagrantfile(self, pubkey, hosts):
        templateLoader = jinja2.BaseLoader()
        template = jinja2.Environment(loader=templateLoader, trim_blocks=True).from_string(VAGRANT_FILE)
        privkey = pubkey
        if privkey.endswith('.pub'):
            privkey = privkey[:-4]
        outputText = template.render(privkey=privkey, pubkey=pubkey, hosts=hosts)

        f = open('Vagrantfile', 'w')
        f.write(outputText)
        f.close()
