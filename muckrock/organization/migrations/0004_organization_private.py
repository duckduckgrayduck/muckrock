# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2017-05-08 21:17


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0003_auto_20151116_2024'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='private',
            field=models.BooleanField(default=False),
        ),
    ]
