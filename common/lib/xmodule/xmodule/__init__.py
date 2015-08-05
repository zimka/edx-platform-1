def use_custom_grading(name):
    """
    Conditional decorator that loads use_custom_grading decorator only when it exists.
    Otherwise, returns empty wrapper.
    """
    try:
        from openedx.core.djangoapps.grading_policy import use_custom_grading  # pylint: disable=import-error
        return use_custom_grading(name)
    except ImportError:
        return lambda f: f
