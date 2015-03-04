#!/bin/bash -ex

if [ "x$1" == "x" ] ; then
    echo "App ID required."
    exit
fi

appid=$1
# old way with Google App Engine SDK
# appcfg.py --oauth2 update -A $appid .
# new way via Google Cloud SDK
# appid = jenkins-watcher
gcloud preview app deploy . --project $appid
# localhost run: gcloud preview app run .