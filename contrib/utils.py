"""
Collection of helper goodies.

"""


import sys
import json
import datetime
import pytz
import logging as log
import traceback
import pprint
from functools import wraps

from google.appengine.api import mail
from google.appengine.api import users

from config import email_recipients, email_sender
from config import access_allowed_domains, access_allowed_users


LOCAL = pytz.timezone("Europe/Prague")
FORMAT = "%Y-%m-%d %H:%M:%S"


def get_current_timestamp_str():
    """
    Returns CET/CEST timestamp string formatted according to format.

    """
    now = datetime.datetime.now()
    return get_localized_timestamp_str(now)
    #datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_localized_timestamp_str(stamp):
    """
    Returns localized timestamp string from stamp (datetime.datetime object
    and local timezone info which is in UTC) formatted according to format.

    """
    local_dt = stamp.replace(tzinfo=pytz.utc).astimezone(LOCAL)
    return LOCAL.normalize(local_dt).strftime(FORMAT)  # .normalize might be unnecessary


def send_email(subject=None, body=None):
    subject = "[jenkins-watcher] %s" % subject
    mail_args = dict(sender=email_sender,
                     subject=subject,
                     body=body,
                     to=email_recipients)
    log.info("Sending email:\n%s" % pprint.pformat(mail_args))
    try:
        mail.send_mail(**mail_args)
        return True
    except:
        log.exception(str(mail_args))
        return False


def access_restriction(handler_method):
    """
    A decorator to require that a user be logged in to access the handler.

    To use it, decorate your get() method like this::

        @access_restriction
        def get(self):
            user = users.get_current_user(self)
            self.response.out.write('Hello, ' + user.nickname())

    We will redirect to a login page if the user is not logged in. We always
    redirect to the request URI, and Google Accounts only redirects back as
    a GET request, so this should not be used for POSTs.

    """
    def check_access_granted(user_email):
        if user_email in access_allowed_users:
            return True
        user_name, user_domain = user_email.split('@')
        for domain in access_allowed_domains:
            if domain == user_domain:
                return True
        return False

    def check_login(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            # doesn't appear in the app engine logs when it's caught
            # by app engine due to app.yaml url handler directives
            msg = "Access from anonymous user, redirecting to login page."
            log.info(msg)
            return self.redirect(users.create_login_url(self.request.url))
        if check_access_granted(user.email()):
            log.info("Access from user '%s' ... granted." % user.email())
            handler_method(self, *args, **kwargs)
        else:
            msg = "User '%s' access denied." % user.email()
            log.warn(msg)
            self.return_json_error(401, msg)
            # self.abort(401, detail=msg)

    return check_login


def exception_catcher(handler_method):
    """
    Used as decorator, critical section is run from here in the
    try-except block and an email is sent if an exception occurs.

    Not designed for nested calls which return values each other.
    NoneType will be returned.

    """
    # without this: AttributeError: 'JenkinsInterface' object has no attribute 'inner'
    #@wraps(handler_method)
    def inner(self, *args, **kwargs):
        try:
            handler_method(self, *args, **kwargs)
        except Exception as ex:
            subject = "exception occurred"
            # trace = ''.join(traceback.format_exception(*sys.exc_info()))
            body = str(ex) + "\n\n" + traceback.format_exc()
            send_email(subject=subject, body=body)
            log.exception(ex)
            self.return_json_error(500, "Internal application error occurred.")

    return inner