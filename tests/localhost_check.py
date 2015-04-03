import time
import urllib2

localhost_url = "http://localhost:8080"
app_yaml = "../app.yaml"

lines = open(app_yaml, 'r').readlines()
for line in lines:
    if line.find("- url:") == -1:
        continue
    url = line.split(": ")[1].strip()
    if url == "/.*":
        url = "/"
    url = "%s%s" % (localhost_url, url)
    print url
    print "checking ..."
    req = urllib2.Request(url)
    # TODO:
    # spits out the page with login request ...
    # provide test credentials and check responses
    print urllib2.urlopen(req).read()
    print "waiting ..."
    time.sleep(5)