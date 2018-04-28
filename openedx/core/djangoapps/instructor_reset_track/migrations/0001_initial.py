# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='InstructorResetStudentAttempts',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('instructor_username', models.CharField(max_length=50)),
                ('student_username', models.CharField(max_length=50)),
                ('block_id', models.CharField(max_length=300)),
                ('course_id', models.CharField(max_length=150)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(max_length=16, choices=[(b'delete', b'delete'), (b'reset', b'reset')])),
            ],
        ),
    ]
