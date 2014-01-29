import datetime
import logging
import StringIO
from django.contrib import messages
import dropbox
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