# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0008_schema__remove_badges'),
        ('instructor_scoring', '0004_studentcourseresultoverride'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentcourseresultoverride',
            name='whitelist',
            field=models.ForeignKey(default=None, to='certificates.CertificateWhitelist'),
            preserve_default=False,
        ),
    ]
