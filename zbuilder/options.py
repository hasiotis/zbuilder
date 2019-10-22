import click


class State(object):
    def __init__(self):
        self.verbose = False
        self.limit = None
        self.vars = None
        self.cfg = None


pass_state = click.make_pass_decorator(State, ensure=True)


def verbose_option(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.verbose = value
        return value
    return click.option('-v', '--verbose', count=True, expose_value=False, help='Enables verbose', callback=callback)(f)


def limit_option(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.limit = value
        return value
    return click.option('-l', '--limit', default=None, expose_value=False, help='Limit selected hosts to a pattern', callback=callback)(f)


def common_options(f):
    f = verbose_option(f)
    f = limit_option(f)
    return f
