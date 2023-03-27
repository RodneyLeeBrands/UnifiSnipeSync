from pyunifi.controller import Controller
#I used this to test various connections to the controller. It was not well documented what "version" of the api Cloud Key Gen 2 Plus uses. You might need to use this as well to quickly try lots of optoins
 
c = Controller('x.x.x.x', 'snipeitsync', 'password', 443, 'UDMP-unifiOS', 'default', False)
for ap in c.get_aps():
	print('AP named %s with MAC %s' % (ap.get('name'), ap['mac']))