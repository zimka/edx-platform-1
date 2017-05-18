# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_scoring', '0007_auto_20170518_1145'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentgradeoverwrite',
            name='course_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
    ]
