from distutils.core import setup

setup(name='fastapp',
      version='0.3',
      py_modules=['fastapp'],
      install_requires=['dropbox==1.6', 
      					'requests==2.0.1', 
      					'django_extensions==1.1.1', 
						'pusher==0.8',
						'mongoengine==0.8.6',
						'pymongo==2.6.3'
						]
)
