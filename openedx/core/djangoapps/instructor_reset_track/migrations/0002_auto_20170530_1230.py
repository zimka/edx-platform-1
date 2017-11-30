# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instructor_reset_track', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='instructorresetstudentattempts',
            name='removed_answer',
            field=models.TextField(default=b''),
        ),
        migrations.AddField(
            model_name='instructorresetstudentattempts',
            name='success',
            field=models.BooleanField(default=False),
        ),
    ]
