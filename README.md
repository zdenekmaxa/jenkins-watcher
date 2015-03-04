Jenkins CI watcher application

Periodically checks number of queued projects on the CI server.

Periodically check how long are the currently running Jenkins
    projects being run. Alerts about and aborts projects taking
    too long to complete.
    
Jenkins server access credentials and Jenkins projects names
are defined in the private config.py file.