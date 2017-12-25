from django.conf.urls import url, patterns
from .views import SuspiciousMonitorFragmentView, suspicious_monitor_view

urlpatterns = patterns(
    'npoed_session_monitor.views',
    url(
        r'suspicious_monitor_fragment_view$',
        SuspiciousMonitorFragmentView.as_view(),
        name='suspicious_monitor_fragment_view'
    ),
    url(r'', 'suspicious_monitor_view', name='suspicious_monitor_view'),
)