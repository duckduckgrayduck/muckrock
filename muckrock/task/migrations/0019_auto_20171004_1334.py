# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-10-04 13:34


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0018_auto_20161211_0913'),
    ]

    operations = [
        migrations.AlterField(
            model_name='responsetask',
            name='predicted_status',
            field=models.CharField(blank=True, choices=[(b'started', b'Draft'), (b'submitted', b'Processing'), (b'ack', b'Awaiting Acknowledgement'), (b'processed', b'Awaiting Response'), (b'appealing', b'Awaiting Appeal'), (b'fix', b'Fix Required'), (b'payment', b'Payment Required'), (b'lawsuit', b'In Litigation'), (b'rejected', b'Rejected'), (b'no_docs', b'No Responsive Documents'), (b'done', b'Completed'), (b'partial', b'Partially Completed'), (b'abandoned', b'Withdrawn')], max_length=10, null=True),
        ),
    ]
