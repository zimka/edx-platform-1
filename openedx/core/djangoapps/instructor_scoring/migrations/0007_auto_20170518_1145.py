# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('instructor_scoring', '0006_auto_20170517_1405'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentgradeoverwrite',
            name='location',
            field=xmodule_django.models.UsageKeyField(default=None, max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='studentgradeoverwrite',
            name='user',
            field=models.OneToOneField(default=None, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='studentgradeoverwrite',
            unique_together=set([('user', 'location')]),
        ),
        migrations.RemoveField(
            model_name='studentgradeoverwrite',
            name='student_module',
        ),
    ]
