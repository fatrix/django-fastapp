import datetime
import logging
import dropbox
import pusher
import StringIO
import hashlib
from django.contrib import messages
from django.conf import settings
from dropbox.rest import ErrorResponse


class UnAuthorized(Exception):
    pass


class NotFound(Exception):
    pass


class NoBasesFound(Exception):
    pass


class Connection(object):

    def __init__(self, access_token):
        self.client = dropbox.client.DropboxClient(access_token)
        super(Connection, self).__init__()

    def info(self):
        account_info = self.client.account_info()
        email = account_info['email']
        name = account_info['display_name']
        return email, name

    def listing(self):
        bases = []
        for base in self._call('metadata', '/')['contents']:
            bases.append(base['path'].lstrip('/'))
        if len(bases) == 0:
            raise NoBasesFound()
        return bases

    def get_file(self, path):
        return self._call('get_file', path).read()

    def put_file(self, path, content):
        f = StringIO.StringIO(content)
        return self._call('put_file', path, f, True)

    def delete_file(self, path):
        return self._call('file_delete', path)

    def create_folder(self, path):
        return self._call('file_create_folder', path)

    def _call(self, ms, *args):
        try:
            m = getattr(self.client, ms)
            return m(*args)
        except ErrorResponse, e:
            print e.__dict__['status']
            if e.__dict__['status'] == 401:
                raise UnAuthorized(e.__dict__['body']['error'])
            if e.__dict__['status'] == 404:
                raise NotFound(e.__dict__['body']['error'])
            raise e
        except Exception, e:
            raise e


def message(request, level, message):
    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if level == logging.ERROR:
        tag = "alert-danger"
    elif level == logging.INFO:
        tag = "alert-info"
    elif level == logging.WARN:
        tag = "alert-info"
    messages.error(request, dt + " " + str(message)[:1000], extra_tags="%s safe" % tag)

def sign(data):
    m = hashlib.md5()
    m.update(data)
    m.update(settings.SECRET_KEY)
    return "%s-%s" % (data, m.hexdigest()[:10])

def channel_name_for_user(request):
    if request.user.is_authenticated():
        channel_name = "%s-%s" % (request.user.username, sign(request.user.username))
    else:
        #channel_name = "anon-%s" % sign(request.session.session_key)
        # TODO: find a way to identify anonymous user
        #     problem on initial
        channel_name = "anon-%s" % sign(request.META['REMOTE_ADDR'])
    return channel_name


def user_message(level, username, message):

    channel = username
    # TODO: strip message to max 10KB
    # http://pusher.com/docs/server_api_guide/server_publishing_events

    p = pusher.Pusher(
      app_id=settings.PUSHER_APP_ID,
      key=settings.PUSHER_KEY,
      secret=settings.PUSHER_SECRET
    )

    now = datetime.datetime.now()
    if level == logging.INFO:
        class_level = "info"        
    elif level == logging.DEBUG:
        class_level = "debug"        
    elif level == logging.WARNING:
        class_level = "warn"        
    elif level == logging.ERROR:
        class_level = "error"        

    p[channel].trigger('console_msg', {'datetime': str(now), 'message': str(message), 'class': class_level})

def info(username, gmessage): 
        return user_message(logging.INFO, username, gmessage)
def debug(username, gmessage): 
        return user_message(logging.DEBUG, username, gmessage)
def error(username, gmessage): 
        return user_message(logging.ERROR, username, gmessage)
def warn(username, gmessage): 
        return user_message(logging.WARN, username, gmessage)