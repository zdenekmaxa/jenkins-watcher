jenkins-watcher app dependencies

file name of the dependencies needs to be correctly set in the config.py file

jenkinsapi-0.2.25-py2.7.egg
    jenkins CI server API library. makes very many requests to the server.
    adjusted HTTP timeout value - experienced HTTP connection issue [1]

pytz-2014.10-py2.7.egg
    dependency of jenkinsapi
    
requests-2.3.0-py2.7.egg
    dependency of jenkinsapi
    the egg archived packed from requests directory as provided with the
    Google Cloud SDK (0.9.49 (2015/02/25)
    standard requests library fails on App Engine due to lack of ssl library,
    the SDK version contains everything
    requests library is available in the SDK but not in production App Engine
    adjusted adapters.py - number of retries due to issue [1]

[1] http://stackoverflow.com/questions/26164000/deadline-exceeded-while-waiting-for-http-response-from-url-httpexception/28849670#28849670