Description
-----------
This app watches student's behavior during the exams and if it is suspicious saves info about the incidents.

It is up to staff to make any decisions about suspicious behavior.
Currently it checks if there were several web sessions during the exam (which possibly means that student haven't passed exam himself) and saves info about these sessions.
To save already seen sessions it uses cache.

Installation
------------

1. Add 'openedx.core.djangoapps.npoed_session_monitor' to the INSTALLED_APPS variable

  ::

    INSTALLED_APPS += ('lms.djangoapps.npoed_session_monitor'',)

2. Add npoed_session_monitor.decorator.npoed_session_monitoring to edx_proctoring.views.StudentProctoredExamAttemptCollection.get

  ::

    edx_proctoring.views.py:

        from lms.djangoapps.npoed_session_monitor.decorator import npoed_session_monitoring

        class StudentProctoredExamAttemptCollection(AuthenticatedAPIView):
        ...
        @npoed_session_monitoring
        def get(self, request):  # pylint: disable=unused-argument
            ...

3. Run migrations

  ::

    python manage.py lms migrate npoed_session_monitoring --settings=YOUR_SETTINGS

4. Add string into Open_edX.egg-info/entry_points.txt (or run pip install -e /edx/app/edxapp/edx-platform)

  ::

     suspicious_monitor = lms.djangoapps.npoed_session_monitor.plugins:SuspiciousMonitorTab
