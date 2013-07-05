from google.appengine.ext import ndb
from google.appengine.api.users import User
import datetime
import hashlib
from dateutil.relativedelta import relativedelta
from secrets import *
from myUtil import *

#######################################
#
# Dummy ancestor
#
#######################################
class DummyAncestor(ndb.Model):
	name=ndb.IntegerProperty(default=1)

#######################################
#
# User management models
#
#######################################

class Contact(ndb.Model):
	# key_name will be the user_id()
	email=ndb.StringProperty() # user email
	nickname=ndb.StringProperty() # user name
	communication=ndb.PickleProperty(default={'Phone':''}) # a dict

#######################################
#
# Abstract models
#
#######################################
class MyBaseModel(ndb.Model):
	# two time stamps
	created_time=ndb.DateTimeProperty(default=datetime.datetime.now())
	last_modified_time=ndb.DateTimeProperty(auto_now=True)
	
	# object owner tied to a Contact
	owner=ndb.KeyProperty(kind='Contact')
	last_modified_by=ndb.KeyProperty(kind='Contact')

	# age since inception, in seconds
	# http://docs.python.org/2/library/datetime.html#datetime.timedelta.total_seconds
	age=ndb.ComputedProperty(lambda self: (datetime.datetime.now()-self.created_time).total_seconds())

	def audit_me(self,contact_key,field_name,old_value,new_value):
		my_audit=MyAudit(parent=self.key)
		my_audit.owner=contact_key
		my_audit.field_name=field_name
		my_audit.old_value=old_value
		my_audit.new_value=new_value
		my_audit.put_async() # async auditing
		
#######################################
#
# Business transaction models
#
#######################################
class MyLetterSecret(ndb.Model):
	# this is the key of this design!
	# that receiver will get an email of this question
	# that is supposed that only the sender and receiver know about
	# thus as a way to validate identity
	# also, this gives receiver a chance NOT TO receive
	# the actual letter if she chooses not to follow the link
	question=ndb.StringProperty(required=True)
	answer=ndb.StringProperty(required=True)
	unlocked_date=ndb.DateTimeProperty()

class MyLetter(MyBaseModel):
	content=ndb.TextProperty(required=True)
	
	# time control
	expected_delivery=ndb.DateProperty(required=True)
	age_count_down=ndb.ComputedProperty(lambda self: (datetime.datetime.combine(self.expected_delivery,datetime.time.min)-datetime.datetime.today()).total_seconds())
	
	# destination
	# can be multiple emails
	receiver_emails=ndb.StringProperty(repeated=True)	

	# generate a random secret string
	# so when sending a nofication to receiver, this random
	# url will be used -- letter will only be served through this url
	# and handler will first check secret matching!
	random_secret=ndb.StringProperty(default=hashlib.sha224(id_generator(100)).hexdigest())
	
	# user set letter secrets
	# one letter can have multiple secrets
	# only when all secrets were answered correctly will we serve the actual letter to receiver
	user_secrets=ndb.KeyProperty(kind='MyLetterSecret',repeated=True)
	
	# receiver read confirmation
	# once all secret were unlocked
	# the letter will be served, we then mark a timestamp when this happens
	# if this field !=None, we suppose receiver has read this letter -- end of our service
	user_secret_unlocked=ndb.DateTimeProperty()
	
	# template
	presentation_template=ndb.StringProperty(default='default')

#######################################
#
# Auditing models
#
#######################################
class MyAudit(ndb.Model):
	# when
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	# by whome
	owner=ndb.KeyProperty(kind='Contact')
	# field name
	field_name=ndb.StringProperty(required=True)
	# old value
	old_value=ndb.GenericProperty()
	# new value
	new_value=ndb.GenericProperty()

#######################################
#
# Channel models
#
#######################################
class ChatMessage(ndb.Model):
	created_time=ndb.DateTimeProperty(default=datetime.datetime.now())
	sender_name=ndb.StringProperty(required=True)
	receiver_name=ndb.StringProperty(required=True)
	message=ndb.StringProperty(required=True)
	# age since inception, in seconds
	# this is a precaution if socket onClose does not fire, in which case
	# server will never know the channel has been closed on the client side
	# so we will sweep this record for any age > 2 hours and delete them
	# 2-hour is the default channel lease
	# on client side, once the lease is up, client has to refresh page to get
	# a new token instead of using the same channel token, thus setting age threshold
	# to 2-hour is sufficient 
	age=ndb.ComputedProperty(lambda self: (datetime.datetime.now()-self.created_time).total_seconds())
	is_expired=ndb.ComputedProperty(lambda self: int(self.age)>7200)

class ChatChannel(ndb.Model):
	created_time=ndb.DateTimeProperty(default=datetime.datetime.now())
	client_id=ndb.StringProperty(required=True)
	contact_id=ndb.StringProperty(required=True)
	contact_name=ndb.StringProperty(required=True)
	token=ndb.StringProperty(required=True)
	in_use=ndb.BooleanProperty(default=False)

	# age since inception, in seconds
	# http://docs.python.org/2/library/datetime.html#datetime.timedelta.total_seconds
	age=ndb.ComputedProperty(lambda self: (datetime.datetime.now()-self.created_time).total_seconds())
	
	# expiration: 2 hour inteval
	is_expired=ndb.ComputedProperty(lambda self: float(self.age)>7200)		
	
