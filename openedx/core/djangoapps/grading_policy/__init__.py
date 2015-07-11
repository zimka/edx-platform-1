from stevedore.extension import ExtensionManager
from django.conf import settings


GRADING_POLICY_NAMESPACE = 'openedx.grading_policy'


class GradingPolicyError(Exception):
    """An error occurred in the Grading Policy App."""
    pass


def use_custom_grading(method_name):
    """Uses a custom grading algorithm or native depends on settings."""
    def decorator(func):
        def wrapper(*args, **kwargs):
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
        raise GradingPolicyError("Unrecognized grader {0}".format(name))


def get_grading_type():
    """Returns grading type depends on settings."""
    if settings.FEATURES['ENABLE_CUSTOM_GRADING']:
        allowed_types = settings.GRADING_ALLOWED_TYPES
        grading_type = settings.GRADING_TYPE
        if grading_type in allowed_types:
            return grading_type
        else:
            raise GradingPolicyError(
                "You must define valid GRADING_TYPE, your type {}, allowed_types are {}".format(
                    grading_type, allowed_types
                )
            )
    return 'sequential'
