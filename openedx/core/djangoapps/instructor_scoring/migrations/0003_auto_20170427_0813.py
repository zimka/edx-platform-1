# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_scoring', '0002_auto_20170427_0752'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentgradeoverride',
            name='current_grade',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='studentgradeoverride',
            name='original_grade',
            field=models.FloatField(default=0),
        ),
    ]
