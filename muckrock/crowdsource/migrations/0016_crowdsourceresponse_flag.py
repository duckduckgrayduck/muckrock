# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-23 19:18


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crowdsource', '0015_auto_20180517_1437'),
    ]

    operations = [
        migrations.AddField(
            model_name='crowdsourceresponse',
            name='flag',
            field=models.BooleanField(default=False),
        ),
    ]
