# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('npoed_session_monitor', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='suspiciousexamattempt',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
    ]
