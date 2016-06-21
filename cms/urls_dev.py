"""
URLconf for development-only views.
This gets imported by urls.py and added to its URLconf if we are running in
development mode; otherwise, it is ignored.
"""
from django.conf.urls import url
from django.conf import settings
from course_validator import course_validator

urlpatterns = (
    url(r'^dev_mode$', 'contentstore.views.dev.dev_mode', name='dev_mode'),
    url(r'^template/(?P<template>.+)$', 'openedx.core.djangoapps.debug.views.show_reference_template'),
    url(r'^course/{}?/check_course$'.format(settings.COURSE_KEY_PATTERN), course_validator, name='course_validator'),

)
