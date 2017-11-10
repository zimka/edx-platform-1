# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_groups', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseusergroup',
            name='group_type',
            field=models.CharField(max_length=20, choices=[(b'cohort', b'Cohort'), (b'shift', b'Shift')]),
        ),
    ]
