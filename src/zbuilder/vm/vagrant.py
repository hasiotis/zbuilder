# flake8: noqa
import click
import shutil
import jinja2

from pathlib import Path
from zbuilder.base import VMProvider
from zbuilder.helpers import runCmd

VAGRANT_FILE_TMPL = "Vagrantfile.tmpl"
VAGRANT_FILE = """
require "shellwords"

VAGRANTFILE_API_VERSION = "2"

Vagrant.require_version ">= 2.2.7"

module ZBuilderDhcpServerMatches
  def dhcp_server_matches_config?(dhcp_server, config)
    true
  end
end

vbox_network_action = VagrantPlugins::ProviderVirtualBox::Action::Network
unless vbox_network_action.private_method_defined?(:dhcp_server_matches_config?) || vbox_network_action.method_defined?(:dhcp_server_matches_config?)
  raise "Vagrantfile: the VirtualBox DHCP workaround is stale - dhcp_server_matches_config? no longer exists in Vagrant #{Vagrant::VERSION}"
end
vbox_network_action.prepend(ZBuilderDhcpServerMatches)

# Disk sizes arrive as a string ("10" or "10,20"). Parse strictly so a typo
# fails with a readable message instead of silently becoming a 0-sized disk.
def zbuilder_disk_sizes(spec, zname)
  spec.to_s.split(",").map(&:strip).reject(&:empty?).map do |entry|
    size = begin
      Integer(entry, 10)
    rescue ArgumentError, TypeError
      raise "Vagrantfile: #{zname}: invalid disk size #{entry.inspect} (expected an integer number of GB)"
    end
    raise "Vagrantfile: #{zname}: disk size must be > 0, got #{size}" unless size > 0
    size
  end
end

ZBUILDER_IP_TRIES = 60
ZBUILDER_IP_DELAY = 2

def zbuilder_guest_ip(vm_id)
  ZBUILDER_IP_TRIES.times do |attempt|
    out = `VBoxManage guestproperty get #{Shellwords.escape(vm_id)} "/VirtualBox/GuestInfo/Net/1/V4/IP" 2>/dev/null`
    ip = out[/^Value:\\s*(\\S+)/, 1]
    return ip if ip
    sleep ZBUILDER_IP_DELAY unless attempt == ZBUILDER_IP_TRIES - 1
  end
  nil
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vagrant.plugins = ["vagrant-hostmanager"]

  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.ignore_private_ip = true
  config.hostmanager.include_offline = true
  config.ssh.insert_key = false
  config.ssh.private_key_path = ["{{ privkey }}", "~/.vagrant.d/insecure_private_key"]

  zservers = {
{% for h, p in hosts.items() %}
    :'{{ h }}' {{ ' ' * (20 - h|string|count) }}  => { memory: {{ p['memory'] }}, vcpus: {{ p['vcpus'] }}, box: '{{ p['box'] }}', aliases: '{{ p['aliases']|default('') }}', disks: '{{ p['disks']|default('') }}', nics: {{ p['nics']|default(1) }} },
{% endfor %}
  }

  zservers.each do |zname, zparam|
    config.vm.define zname do |srvcfg|
      nics = zparam[:nics].to_i

      srvcfg.vm.box = zparam[:box]
      srvcfg.vm.hostname = zname.to_s

      nics.times do
        srvcfg.vm.network :private_network, type: "dhcp"
      end

      # Replaces the box's insecure key, hence ssh.insert_key = false above and
      # the private key listed first in ssh.private_key_path.
      srvcfg.vm.provision "file", source: "{{ pubkey }}", destination: ".ssh/authorized_keys"

      domain = zname.to_s.sub(/^.*?\\./, "")
      srvcfg.hostmanager.aliases = zparam[:aliases].split(" ").map { |a| "#{a}.#{domain}" }

      # Vagrant creates, attaches and cleans these up per machine, picking a free
      # port on whatever storage controller the box actually uses.
      zbuilder_disk_sizes(zparam[:disks], zname).each_with_index do |size, idx|
        srvcfg.vm.disk :disk, name: "disk#{idx + 2}", size: "#{size}GB"
      end

      srvcfg.vm.provider "virtualbox" do |v|
        v.name = zname.to_s
        v.memory = zparam[:memory]
        v.cpus = zparam[:vcpus]
        v.customize ["modifyvm", :id, "--graphicscontroller", "vmsvga"]
        v.customize ["modifyvm", :id, "--vram", "64"]
        v.customize ["modifyvm", :id, "--vrde", "off"]
        # Host resolver takes precedence over the DNS proxy; enable only one.
        v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
        # Adapter 1 is NAT, adapters 2..n+1 are the private networks above.
        (1..nics + 1).each do |n|
          v.customize ["modifyvm", :id, "--nictype#{n}", "virtio"]
        end
      end

      srvcfg.hostmanager.ip_resolver = proc do |vm, _resolving_vm|
        next nil unless vm.id
        ip = zbuilder_guest_ip(vm.id)
        if ip.nil?
          warn "hostmanager: no guest IP for #{vm.name} (not running, or guest additions unavailable) - skipping /etc/hosts entry"
        end
        ip
      end
    end
  end
end
"""


class vmProvider(VMProvider):
    def _cmd(self, hosts, cmd):
        self.setVagrantfile(pubkey=self.cfg["state"].vars["ZBUILDER_PUBKEY"], hosts=hosts)
        for h in hosts:
            if hosts[h]["enabled"]:
                click.echo("  - Host: {}".format(h))
                runCmd(cmd.format(host=h), verbose=self.cfg["state"].verbose)

    def build(self, hosts):
        self._cmd(hosts, "vagrant up {host}")

    def up(self, hosts):
        self._cmd(hosts, "vagrant up {host}")

    def halt(self, hosts):
        self._cmd(hosts, "vagrant halt {host}")

    def destroy(self, hosts):
        self._cmd(hosts, "vagrant destroy --force {host}")

    def dnsupdate(self, hosts):
        self._cmd(hosts, "vagrant hostmanager {host}")

    def snapCreate(self, hosts):
        self._cmd(hosts, "vagrant snapshot save {host} zbuilder --force")

    def snapRestore(self, hosts):
        click.echo("  Halting")
        self._cmd(hosts, "vagrant halt {host}")
        click.echo("  Restoring")
        self._cmd(hosts, "vboxmanage snapshot {host} restore zbuilder")
        click.echo("  Booting up")
        self._cmd(hosts, "vboxmanage startvm {host} --type headless")

    def snapDelete(self, hosts):
        self._cmd(hosts, "vagrant snapshot delete {host} zbuilder")

    def params(self, params):
        if "disks" in params.keys():
            return {k: params[k] for k in ["box", "vcpus", "memory", "disks"]}
        else:
            return {k: params[k] for k in ["box", "vcpus", "memory"]}

    def config(self):
        return shutil.which("vagrant")

    def status(self):
        if shutil.which("vagrant"):
            return "PASS"
        else:
            return "Vagrant binary not found"

    def setVagrantfile(self, pubkey, hosts):
        global VAGRANT_FILE
        if Path(VAGRANT_FILE_TMPL).exists():
            VAGRANT_FILE = Path(VAGRANT_FILE_TMPL).read_text()
        templateLoader = jinja2.BaseLoader()
        template = jinja2.Environment(loader=templateLoader, trim_blocks=True).from_string(VAGRANT_FILE)
        privkey = pubkey
        if privkey.endswith(".pub"):
            privkey = privkey[:-4]
        outputText = template.render(privkey=privkey, pubkey=pubkey, hosts=hosts)

        f = open("Vagrantfile", "w")
        f.write(outputText)
        f.close()
