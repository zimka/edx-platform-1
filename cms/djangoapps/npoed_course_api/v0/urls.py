from django.conf.urls import patterns, url
from django.conf import settings

from npoed_course_api.v0 import views

COURSE_ID_PATTERN = settings.COURSE_ID_PATTERN

urlpatterns = patterns(
    '',
    url(r'^courses/$', views.CourseManagement.as_view(), name='list'),
    url(r'^courses/{}/$'.format(COURSE_ID_PATTERN), views.CourseManagement.as_view(), name='list'),
)
