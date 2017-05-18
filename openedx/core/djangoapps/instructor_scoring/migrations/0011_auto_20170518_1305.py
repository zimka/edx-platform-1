# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_scoring', '0010_auto_20170518_1256'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='studentcourseresultoverride',
            name='student',
        ),
        migrations.RemoveField(
            model_name='studentcourseresultoverride',
            name='whitelist',
        ),
        migrations.DeleteModel(
            name='StudentCourseResultOverride',
        ),
    ]
