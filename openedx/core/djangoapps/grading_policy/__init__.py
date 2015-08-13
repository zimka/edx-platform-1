"""
Contains useful methods to work with custom grading types.
"""
from stevedore.extension import ExtensionManager
from django.conf import settings


GRADING_POLICY_NAMESPACE = 'openedx.grading_policy'


class GradingPolicyError(Exception):
    """An error occurred in the Grading Policy App."""
    pass


def use_custom_grading(method_name):
    """Uses a custom grading algorithm or native depends on settings."""
    def decorator(func):  # pylint: disable=missing-docstring
        def wrapper(*args, **kwargs):  # pylint: disable=missing-docstring
            if settings.FEATURES['ENABLE_CUSTOM_GRADING']:
                grader = get_grading_class(settings.GRADING_TYPE)
                return getattr(grader, method_name)(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator


def get_grading_class(name):
    """Returns a pluggin by the `name(str)`."""
    extension = ExtensionManager(namespace=GRADING_POLICY_NAMESPACE)
    try:
        return extension[name].plugin
    except KeyError:
        raise GradingPolicyError("Unrecognized grading type `{0}`".format(name))


def get_grading_type():
    """Returns grading type depends on settings."""
    if settings.FEATURES['ENABLE_CUSTOM_GRADING']:
        return settings.GRADING_TYPE
    return 'sequential'
