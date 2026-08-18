import click
import massedit

from zbuilder.base import DNSProvider


class dnsProvider(DNSProvider):
    def update(self, host, zone, ip):
        click.echo("  - Updating record [{}.{}] with ip [{}]".format(host, zone, ip))
        filenames = ["hosts"]
        regex = "re.sub('({}.{}).*(ansible_ssh_host=)?(.*)', r'\\1 \\2ansible_host={}', line)".format(host, zone, ip)
        massedit.edit_files(filenames, [regex], dry_run=False)

    def remove(self, host, zone):
        click.echo("  - Removing record [{}.{}]".format(host, zone))
        filenames = ["hosts"]
        regex = "re.sub('({}.{}).*(ansible_ssh_host=)?(.*)', r'\\1', line)".format(host, zone)
        massedit.edit_files(filenames, [regex], dry_run=False)
