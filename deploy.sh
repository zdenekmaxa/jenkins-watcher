#!/bin/bash -ex

if [ "x$1" == "x" ] ; then
    echo "App ID required."
    exit
fi

appid=$1
version="v0-7"
verbosity=warning
#verbosity=debug

# old way with Google App Engine SDK
# appcfg.py --oauth2 update -A $appid .
# new way via Google Cloud SDK
# appid = jenkins-watcher
# version is no longer part of the app.yaml but specified
# explicitly on CLI

gcloud app deploy ./app.yaml --project $appid --version $version --verbosity $verbosity
# when updating datastore indixes
#gcloud app deploy ./index.yaml --project $appid --version $version --verbosity $verbosity

# localhost run: gcloud app run .

# start on localhost:
# $PREFIX/platform/google_appengine/dev_appserver.py .
