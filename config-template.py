import os

jenkins_url = URL

# jenkins egg file and its dependencies not available on App Engine
egg_files = ["jenkinsapi-0.2.25-py2.7.egg",
             "pytz-2014.10-py2.7.egg",
             "requests-2.3.0-py2.7.egg"]

user_name = USERNAME

access_token = ACCESS_TOKEN

# jenkins job/project names
job_names = [JENKINS_PROJECT_1, JENKINS_PROJECT_2, JENKINS_PROJECT_2]

domains_allow_access = [DOMAIN_1, DOMAIN_2]

email_recipients = [EMAIL_1, EMAIL_2]

email_sender = "zden.maxa@gmail.com"