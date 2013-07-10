# -*- coding: utf-8 -*-
import sys
from secrets import SESSION_KEY

from webapp2 import WSGIApplication, Route

# inject './lib' dir in the path so that we can simply do "import ndb" 
# or whatever there's in the app lib dir.
if 'lib' not in sys.path:
    sys.path[0:0] = ['lib']

# webapp2 config
app_config = {
  'webapp2_extras.sessions': {
    'cookie_name': '_simpleauth_sess',
    'secret_key': SESSION_KEY
  },
  'webapp2_extras.auth': {
    'user_attributes': []
  }
}
    
# Map URLs to handlers
routes = [
	Route('/profile', handler='handlers.ProfileHandler', name='profile'),
	Route('/logout', handler='handlers.AuthHandler:logout', name='logout'),
	Route('/auth/<provider>',handler='handlers.AuthHandler:_simple_auth', name='auth_login'),
	Route('/auth/<provider>/callback', handler='handlers.AuthHandler:_auth_callback', name='auth_callback'),

	# letter controllers
	Route('/blob/serve/<resource:[^/]+>/', handler='hime.BlobServeHandler',name='blobstore-serve'),
	Route('/letter/new',handler='hime.PublishLetterHandler',name='letter-new'),	
	Route('/letter/manage/<owner_id:\d+>/',handler='hime.ManageLetterByOwnerHandler',name='letter-manage-byowner'),	
	Route('/letter/verification/<owner_id:\d+>/<letter_id:\d+>/',handler='hime.VerifySecretHandler',name='letter-secret-verification'),	
	Route('/letter/secret',handler='hime.ValidateLetterSecretHandler',name='letter-secret-validate'),	
	Route('/letter/test',handler='hime.TestLetterHandler',name='letter-test'),	
	
	# user controllers
	Route('/user/contact',handler='hime.ManageUserContact',name='user-contact'),	
	
	# channel controller
	Route('/_ah/channel/connected/',handler='hime.ChannelConnected',name='channel-connected'),
	Route('/_ah/channel/disconnected/',handler='hime.ChannelDisconnected',name='channel-disconnected'),
	Route('/channel/token',handler='hime.ChannelToken',name='channel-token'),	
	Route('/channel/route',handler='hime.ChannelRouteMessage',name='channel-route-message'),	
	Route('/channel/list/onlineusers',handler='hime.ChannelListOnlineUsers',name='channel-list-onlineusers'),
    
	# google wallet
	Route('/wallet/token',handler='anthem.GoogleWalletToken',name='google-wallet-token'),
	Route('/wallet/postback',handler='anthem.GoogleWalletPostback',name='google-wallet-postback'),
                
	# if everything falls out
	Route('/', handler='hime.MainPage'),  
	
]

app = WSGIApplication(routes, config=app_config, debug=True)
