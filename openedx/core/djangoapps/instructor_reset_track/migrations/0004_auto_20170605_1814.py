# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_reset_track', '0003_instructorresetstudentattempts_block_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instructorresetstudentattempts',
            name='action',
            field=models.CharField(max_length=10, choices=[(b'delete', b'delete'), (b'reset', b'reset')]),
        ),
        migrations.AlterField(
            model_name='instructorresetstudentattempts',
            name='block_id',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='instructorresetstudentattempts',
            name='block_url',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='instructorresetstudentattempts',
            name='course_id',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='instructorresetstudentattempts',
            name='timestamp',
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
    ]
