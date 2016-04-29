"""
Notification objects for the messages app
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

import json
import requests

class EmailNotification(EmailMultiAlternatives):
    """A generic base class for composing notification emails."""
    text_template = None
    subject = u'Notification'

    def __init__(self, users, context):
        """Initialize the notification"""
        super(EmailNotification, self).__init__(subject=self.subject)
        if isinstance(users, User):
            self.users = [users]
            self.to = [users.email]
        elif isinstance(users, list):
            # check that all list members are users
            # if not, raise TypeError
            for user in users:
                if not isinstance(user, User):
                    raise TypeError('Notification expects a list of Users')
            self.users = users
            self.to = [user.email for user in users]
        else:
            raise TypeError('Notification requires at least one User to receive it.')
        self.from_email = 'MuckRock <info@muckrock.com>'
        self.bcc = ['diagnostics@muckrock.com']
        self.body = render_to_string(self.get_text_template(), self.get_context_data(context))

    def get_context_data(self, context):
        """Return init keywords and the user-to-notify as context."""
        context['users'] = self.users
        return context

    def get_text_template(self):
        """Every notification should have a text template."""
        if self.text_template is None:
            raise NotImplementedError('Notification requires a text template.')
        else:
            return self.text_template


class SupportNotification(EmailNotification):
    """Send a support email."""
    text_template = 'message/notification/support.txt'
    subject = u'Support'


class ProjectNotification(EmailNotification):
    """Send a project email."""
    text_template = 'message/notification/support.txt'
    subject = u'Pending Project'


class SlackNotification(object):
    """
    Sends a Slack notification, conforming to the platform's specification.
    Slack notifications should be initialized with a payload that contains the notification.
    If they aren't, you still have a chance to update the payload before sending the message.
    Notifications with empty payloads will be rejected by Slack.
    Payload should be a dictionary, and the API is described by Slack here:
    https://api.slack.com/docs/formatting
    https://api.slack.com/docs/attachments
    """
    def __init__(self, payload=None):
        """Initializes the request with a payload"""
        self.endpoint = settings.SLACK_WEBHOOK_URL
        if payload is None:
            payload = {}
        self.payload = payload

    def send(self, fail_silently=True):
        """Send the notification to our Slack webhook."""
        if not self.endpoint:
            # don't send when the endpoint value is empty,
            # or the requests module will throw errors like woah
            return 0
        data = json.dumps(self.payload)
        response = requests.post(self.endpoint, data=data)
        if response.status_code == 200:
            return 1
        else:
            if not fail_silently:
                response.raise_for_status()
            return 0
