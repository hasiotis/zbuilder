import click
import massedit


class dnsProvider(object):
    def __init__(self, state):
        self.state = state

    def update(self, host, zone, ip):
        click.echo("  - Updating record [{}.{}] with ip [{}]".format(host, zone, ip))
        filenames = ['hosts']
        regex = "re.sub('({}.{}).*(ansible_ssh_host=)?(.*)', r'\\1 \\2ansible_host={}', line)".format(host, zone, ip)
        massedit.edit_files(filenames, [regex], dry_run=False)

    def remove(self, host, zone):
        click.echo("  - Removing record [{}.{}]".format(host, zone))
        filenames = ['hosts']
        regex = "re.sub('({}.{}).*(ansible_ssh_host=)?(.*)', r'\\1', line)".format(host, zone)
        massedit.edit_files(filenames, [regex], dry_run=False)
