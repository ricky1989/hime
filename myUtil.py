import babel.dates
import urllib
from dateutil.relativedelta import relativedelta
import datetime
import string,random

CAT={
	'ipad':['electronic','computer','gadget','personal device','portable computer'],
	'iphone':['electronic','computer','gadget','personal device','portalble computer'],
	'poster':['art','interior design','decoration'],
	'g-shock':['watch','sport watch','fashion'],
	'bounty':['supply','cleaning','paper towel'],
	'lcd':['computer','display','monitor','electronic'],
	'redhat':['software','linux'],
	'software':['software','programming'],
	'kitty':['toy','decoration'],
}

def categorization(words):
	# match words to CAT to create a CAT list
	c=[]
	for w in words:
		if w.lower() in CAT: c+=CAT[w.lower()]
	if len(c)==0: c=['uncategoried']
	return list(set(c))

def tokenize(something):
	# always lower case
	# this will make future search case insensitive!
	phrase=something.lower()
	
	# break phrase to list of token
	
	# 1. we save any token delimited by ','
	# eg. "interior decoration, snap,whatever this is"
	by_comma=[p.strip() for p in phrase.split(',')]
	
	# 2. we further breaking down comma delimitered token by white space
	by_whitespace=[]
	for bb in by_comma:
		by_whitespace+=[b.strip() for b in bb.split(' ')]
	
	# we are to merge all lists into one!
	return list(set(by_comma+by_whitespace))

def format_datetime(value, format='medium'):
	if format == 'full':
		format="EEEE, d. MMMM y 'at' HH:mm"
	elif format == 'medium':
		format="EE dd.MM.y HH:mm"
	return babel.dates.format_datetime(value, format)

def id_generator(size=12, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for x in range(size))
