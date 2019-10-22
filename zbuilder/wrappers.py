import click


def trywrap(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AttributeError:
            click.echo("Provider does not implement this action")
        except Exception as e:
            click.echo("Provider failed with [{}]".format(e))
    return wrapper
