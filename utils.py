"""
Collection of helper goodies.

"""


import datetime
import pytz
import logging as log

from google.appengine.api import mail

from config import email_recipients, email_sender

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
    log.info("Sending email:\n%s\n%s" % (subject, body))
    mail_args = dict(sender=email_sender,
                     subject=subject,
                     body=body,
                     to=email_recipients)
    try:
        mail.send_mail(**mail_args)
    except:
        log.exception(str(mail_args))