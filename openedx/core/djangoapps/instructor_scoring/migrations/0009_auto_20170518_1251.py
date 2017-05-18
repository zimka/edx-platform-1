# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_scoring', '0008_studentgradeoverwrite_course_id'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='studentgradeoverwrite',
            unique_together=set([]),
        ),
    ]
