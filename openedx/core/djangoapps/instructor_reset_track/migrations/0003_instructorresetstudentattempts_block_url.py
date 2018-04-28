# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_reset_track', '0002_auto_20170530_1230'),
    ]

    operations = [
        migrations.AddField(
            model_name='instructorresetstudentattempts',
            name='block_url',
            field=models.CharField(default='', max_length=300),
            preserve_default=False,
        ),
    ]
