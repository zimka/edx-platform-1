# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import openedx.core.djangoapps.npoed_session_monitor.models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0007_proctoredexam_proctoring_service'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuspiciousExamAttempt',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('exam_sessions', openedx.core.djangoapps.npoed_session_monitor.models.ExamSessionSetField()),
                ('exam_attempt', models.OneToOneField(to='edx_proctoring.ProctoredExamStudentAttempt')),
            ],
        ),
    ]
