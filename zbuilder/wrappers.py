import click


def trywrap(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except AttributeError as error:
            click.echo("Provider does not implement this action")
        except Exception as e:
            click.echo("Provider failed with [{}]".format(e))
    return wrapper
