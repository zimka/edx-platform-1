from django.conf.urls import url, patterns
from .views import SuspiciousMonitorFragmentView, delete_suspicious_attempt

urlpatterns = patterns(
    'openedx.core.djangoapps.npoed_session_monitor.views',
    url(
        r'suspicious_monitor_fragment_view$',
        SuspiciousMonitorFragmentView.as_view(),
        name='suspicious_monitor_fragment_view'
    ),
    url(r'delete_suspicious_attempt', delete_suspicious_attempt, name='delete_suspicious_attempt'),
    url(r'', 'suspicious_monitor_view', name='suspicious_monitor_view'),
)