import traceback


def trywrap(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AttributeError:
            raise Exception("Provider does not implement this action")
        except Exception:
            traceback.print_exc()

    return wrapper
