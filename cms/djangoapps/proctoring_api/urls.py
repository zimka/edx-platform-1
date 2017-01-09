"""
CMS Proctoring API URI specification.

Patterns here should simply point to version-specific patterns.
"""
from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    '',
    url(r'^v0/', include('proctoring_api.v0.urls', namespace='v0'))
)
