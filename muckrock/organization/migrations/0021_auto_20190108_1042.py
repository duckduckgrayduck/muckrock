# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2019-01-08 15:42


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0020_remove_organization_plan'),
    ]

    operations = [
        migrations.RenameField(
            model_name='organization',
            old_name='new_plan',
            new_name='plan',
        ),
    ]
