from django.conf.urls import url, patterns
from .views import SuspiciousMonitorFragmentView

urlpatterns = patterns(
    'npoed_session_monitor.views',
    url(
        r'suspicious_monitor_fragment_view$',
        SuspiciousMonitorFragmentView.as_view(),
        name='suspicious_monitor_fragment_view'
    ),
    url(r'', 'suspicious_monitor_view', name='suspicious_monitor_view'),
)