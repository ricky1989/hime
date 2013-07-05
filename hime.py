import webapp2
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.api import images
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.blobstore import delete, delete_async
from google.appengine.api import channel
from webapp2 import uri_for,redirect
import os
import urllib
import json
import cgi
import logging
import datetime

import jinja2
from models import *
from myUtil import *

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])


####################################################
#
# Static Page Controllers
#
####################################################

class MainPage(webapp2.RequestHandler):
	def get(self):
		template = JINJA_ENVIRONMENT.get_template('/template/Home.html')
		self.response.write(template.render())

		
####################################################
#
# Base Controllers
#
####################################################

class BlobServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
	def get(self, resource):
		# resource is actually a blobkey
  		resource = str(urllib.unquote(resource))
  		blob_info = blobstore.BlobInfo.get(resource)
  		self.send_blob(blob_info)
                      
class ComplexEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.date):
			epoch = datetime.datetime.utcfromtimestamp(0)
			delta = obj - epoch
			return delta.total_seconds()
			#return obj.isoformat()
		elif isinstance(obj,datetime.datetime):
			epoch = datetime.datetime.utcfromtimestamp(0)
			delta = obj - epoch
			return delta.total_seconds()
		elif isinstance(obj,users.User):
			return {'email':obj.email(),'id':obj.user_id(),'nickname':obj.nickname()}
		elif isinstance(obj,ndb.Key):
			if obj.kind()=='Contact':
				contact=obj.get()
				return {'name':contact.nickname,'email':contact.email,'id':contact.key.id()}
			elif obj.kind()=='BuyOrder':
				o=obj.get()
				return {'name':o.name,'description':o.description,'id':o.key.id(),'owner':o.owner}
		else:
			return json.JSONEncoder.default(self, obj)

class MyBaseHandler(webapp2.RequestHandler):
	def __init__(self, request=None, response=None):
		webapp2.RequestHandler.__init__(self,request,response) # extend the base class
		self.template_values={}		
		self.template_values['user']=self.user = users.get_current_user()
		self.template_values['me']=self.me=self.get_contact()
		self.template_values['url_login']=users.create_login_url(self.request.url)
		self.template_values['url_logout']=users.create_logout_url('/')
		
	def get_contact(self):
		# manage contact -- who is using my service?
		# update email and user name
		# this is to keep Google user account in sync with internal Contact model
		user = self.user
		me=Contact.get_or_insert(ndb.Key('Contact',user.user_id()).string_id(),
			email=user.email(),
			nickname=user.nickname())
			
		return me

class PublishLetterHandler(MyBaseHandler):
	def get(self):
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/PublishLetter.html')
		self.response.write(template.render(self.template_values))
	def post(self):
		content=self.request.get('content')

		try:
			delivery_date=datetime.datetime.strptime(self.request.POST['delivery_date'],'%Y-%m-%d').date()
   		except:
   			delivery_date=datetime.datetime.strptime(self.request.POST['delivery_date'],'%m/%d/%Y').date()
   			
		emails=self.request.get('receiver_email')
		
		# create secrets
		secrets=[]
		for i in range(3):
			s=MyLetterSecret(
				parent=ndb.Key('DummyAncestor','SecretRoot'),
				question='who',
				answer='me')
			secrets.append(s)
		ndb.put_multi(secrets)
		
		# create letter
		letter=MyLetter(parent=self.me.key,
			owner=self.me.key,
			content=content,
			expected_delivery=delivery_date,
			receiver_emails=emails.split(','),
			user_secrets=[s.key for s in secrets])
		letter.put()

		self.response.write('0')				
####################################################
#
# User/Membership Controllers
#
####################################################

class ManageUserContact(MyBaseHandler):
	def get(self):
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageUserContact.html')
		self.response.write(template.render(self.template_values))

	def post(self):
		self.me.communication=self.request.POST
		self.me.put()
		self.response.write('0')


####################################################
#
# Channel controllers
#
####################################################

def send_chat(sender,receiver,message):
		# look up live receiver channel by name
		queries=ChatChannel.query(ChatChannel.contact_name==receiver, ChatChannel.in_use==True)
		
		if queries.count()>0:
			for c in queries:
				# receiver live channel found
				channel.send_message(c.client_id,json.dumps({'sender':sender,'message':message}))
			return queries.count()
		else:
			return 0
			
# free app max list length will be 100
# so iteration shouldn't be too bad
# client_id: {'contact_id':user, 'contact_name': nickname, 'token':token, 'in_use':False, 'created_time':created_time)
chat_channel_pool={}

class ChannelConnected(webapp2.RequestHandler):
	def post(self):
		client_id=self.request.get('from')
		queries=ChatChannel.query(ChatChannel.client_id==client_id)
		if queries.count()==0: return
		
		assert queries.count()==1
		saved_channel=queries.get()
		
		# check channel age
		# max 2-hour
		if saved_channel.is_expired: 
			saved_channel.key.delete()
			
			# tell client this channel has expired
			self.response.write('-1')
			return
			
		# set channel to in_use
		saved_channel.in_use=True
		saved_channel.put()	
		
		logging.info('Connected: '+client_id)
						
class ChannelDisconnected(webapp2.RequestHandler):
	def post(self):
		client_id=self.request.get('from')
		
		queries=ChatChannel.query(ChatChannel.client_id==client_id)
		if queries.count()==0: return

		assert queries.count()==1
		saved_channel=queries.get()

		# check channel age
		# max 2-hour
		if saved_channel.is_expired: 
			saved_channel.key.delete()
			
			# tell client this channel has expired
			self.response.write('-1')
			return
			
		# set channel to in_use
		saved_channel.in_use=False
		saved_channel.put()	
		
		logging.info('Disconnected: '+client_id)
		
class ChannelToken(webapp2.RequestHandler):
	# This is the token pool management controller.
	# client page will POST to request a token to use
	# we will look up the pool for usable channel, if nothing, we'll create a new one.
	# Further, a client_id can have max 2 open channels -- this essentially limits
	# how many browser tabs a user can open while still have a usable chat on that page.
	def post(self):
		# who is requesting?
		contact_id=self.request.get('contact_id')
		contact_name=self.request.get('contact_name')
		
		# let's find a channel for this user
		token=None
		opened_channel_count=0
		
		all_saved_channel=ChatChannel.query()
		queries=all_saved_channel.filter(ChatChannel.contact_id==contact_id)
		for c in queries:
			if c.in_use is False:
				# unused channel, validate its age
				if c.is_expired:
					c.key.delete()
				else: 
					token=c.token
					break # we found a valid token to use
			else: opened_channel_count +=1
				
		# no reusable channel for this contact_id
		if token is None:
			if all_saved_channel.count()>=100:
				# we have hit the max quota, tell user he can not chat, sorry
				self.response.write('-2')
			elif opened_channel_count <2:
				# create a new one
				# has quota, create one and add to the pool
				random_id=contact_id+id_generator()
				random_token = channel.create_channel(random_id)
				 
				# add to pool
				c=ChatChannel(client_id=random_id, contact_id=contact_id,contact_name=contact_name,token=random_token)
				c.put()
				 
				# tell client token
				logging.info('Issuing new token: '+random_token)
				self.response.write(random_token)
			
			else: # user has 2 open channel already, deny new request
				self.response.write('-1')
		else:
			logging.info('Reuse token: '+token)
			self.response.write(token)
				
class ChannelRouteMessage(webapp2.RequestHandler):
	def post(self):
		sender=self.request.get('sender').strip()
		receiver=self.request.get('receiver').strip()[1:]
		message=self.request.get('message').strip()
		
		# user offline
		if send_chat(sender,receiver,message)==0:
			self.response.write('-1')

