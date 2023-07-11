# import requests module
import requests
 
# create a session object
s = requests.Session()
 
# make a get request
r = s.get('https://www.apkmirror.com/apk/red-apps-ltd/sync-for-reddit/')
 
# again make a get request
print(r.text, flush=True)
