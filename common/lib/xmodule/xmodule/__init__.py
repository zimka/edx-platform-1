"""Contains base helper methods used by xmodules"""


def use_custom_grading(name):
    """
    Conditional decorator that loads use_custom_grading decorator only when it exists.
    Otherwise, returns empty wrapper.
    """
    try:
        # pylint: disable=import-error, redefined-outer-name
        from openedx.core.djangoapps.grading_policy import use_custom_grading
        return use_custom_grading(name)
    except ImportError:
        return lambda f: f
