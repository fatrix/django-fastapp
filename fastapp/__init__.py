__version__ = "0.411"

import pusher
import pika
import threading
from django.conf import settings
from fastapp.models import Base, Executor

#monkey.patch_all()
def get_pusher_instance():
    print "get_pusher"
    p = pusher.Pusher(
      app_id=settings.PUSHER_APP_ID,
      key=settings.PUSHER_KEY,
      secret=settings.PUSHER_SECRET
    )
    return p
pusher_instance = get_pusher_instance()


def callback(ch, method, properties, body):
	payload = body.loads(body)
	channel = payload['channel']
	event = payload['event']
	data = payload['data']
	print "CALLBACK", body
	pusher_instance[channel].trigger(event, data)


def send_events():
	print "START - SEND_EVENTS Consumer"
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()
	channel.basic_consume(callback,
                      queue='pusher_events',
                      #no_ack=True
	)	
	print "END - SEND_EVENTS Consumer"
	
def start_listen_for_events():
	print "Start events dispatcher thread"
	threads = []
	for c in range(1, 10):
		#threads.append(gevent.spawn(send_events))
		#thread.start_new_thread(send_events, ())
		t = threading.Thread(target=send_events, args=())
		t.start()
		threads.append(t)

	#for t in threads:
	#	t.join()
	#

#start_listen_for_events()
