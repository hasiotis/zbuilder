from click.testing import CliRunner
from zbuilder.cli import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'cli, version ' in result.output
