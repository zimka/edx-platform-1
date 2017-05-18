# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_scoring', '0009_auto_20170518_1251'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentgradeoverwrite',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
    ]
