Djend
=====

Installation
------------

Add fastapp to settings.INSTALLED_APPS

         "fastapp",

Install required modules

    pip install -r requirements.txt

Add fastapp to urls.py

         ("^fastapp/", include("fastapp.urls")),

Add  DROPBOX_CONSUMER_KEY and DROPBOX_CONSUMER_SECRET to your settings.py


Usage
-----

1. Login
2. Visit http://YOURURL/djend
