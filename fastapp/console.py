import sys
import json
import pusher
import logging
import pika
import time
import threading
from datetime import datetime

from django.conf import settings

from queue import connect_to_queue

logger = logging.getLogger(__name__)

def get_pusher():
    pusher_instance = None
    if pusher_instance is None:
        logger.info("get_pusher")
        print pusher
        pusher_instance = pusher.Pusher(
          app_id=settings.PUSHER_APP_ID,
          key=settings.PUSHER_KEY,
          secret=settings.PUSHER_SECRET
        )
    #p = pusher.Pusher(
    #  app_id=settings.PUSHER_APP_ID,
    #  key=settings.PUSHER_KEY,
    #  secret=settings.PUSHER_SECRET
    #)
    logger.debug(pusher_instance)
    return pusher_instance

def send_to_pusher(ch, method, props, body):
    logger.info(sys._getframe().f_code.co_name)
    p = get_pusher()    
    body = json.loads(body)

    event = body['event']
    channel = body['channel']
    data = body['data']

    logger.info("trigger")
    p[channel].trigger(event, data)
    logger.info("ack start")
    ch.basic_ack(delivery_tag = method.delivery_tag)
    logger.info("ack done")

def consume(channel):
    logger.info("Start consuming on pusher_events")
    #channel = connect_to_queue('pusher_events')
    #channel.basic_qos(prefetch_count=1) 
    channel.basic_consume(send_to_pusher, queue='pusher_events')
    channel.start_consuming()

def start_sender():
    channel = connect_to_queue('localhost', 'pusher_events')
    from threading import Thread
    logger.info("Start thread for consume")
    t = Thread(target=consume, args=(channel,))
    t.daemon = True
    t.start()
    return t

class PusherSenderThread(threading.Thread):
    PUBLISH_INTERVAL = 20

    def __init__(self, threadID, name, counter, vhost):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter

        self.vhost = vhost

        self.in_sync = False

    def run(self):
        self.parameters = pika.ConnectionParameters(host="localhost", heartbeat_interval=3)
        logger.info("starting " + self.name)

        while True:
            try:
                self._connection = pika.SelectConnection(self.parameters, self.on_connected, on_close_callback=self.on_close)
                logger.info('connected')
            except Exception:
                logger.warning('cannot connect', exc_info=True)
                time.sleep(5)
                continue

            try:
                self._connection.ioloop.start()
            finally:
                pass
                try:
                    self._connection.close()
                    self._connection.ioloop.start() # allow connection to close
                except Exception, e:
                    logger.error("PusherSenderThread lost connection")
                    logger.exception(e)

    def on_close(self, connection, reply_code, reply_text):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)

    def consume_on_queue_declared(self, frame):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        self.channel.basic_consume(self.on_beat, queue='pusher_events', no_ack=True)

    def on_connected(self, connection):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        self._connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        channel.queue_declare(queue='pusher_events', callback=self.consume_on_queue_declared)

        self.channel = channel

    ##def send_message(self):
    #    self.channel.basic_publish(exchange='',
    #            routing_key=HEARTBEAT_QUEUE,
    #            properties=pika.BasicProperties(
    #                #delivery_mode=1,
    #                #reply_to = self.callback_queue,
    #                #correlation_id = self.corr_id,
    #            ),
    #            body=json.dumps({
    #                'in_sync': self.in_sync,
    #                'vhost': self.vhost 
    #                }))
       # self.in_sync = True
    #    self.schedule_next_message()
#
    #def schedule_next_message(self):
    #    """If we are not closing our connection to RabbitMQ, schedule another
    #    message to be delivered in PUBLISH_INTERVAL seconds.
#
#        """
#        #if self._stopping:
#        #    return
#        logger.info('Next beat in %0.1f seconds',
#                    self.PUBLISH_INTERVAL)
#        self._connection.add_timeout(self.PUBLISH_INTERVAL,
#                                     self.send_message)

    def on_beat(self, ch, method, props, body):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        #ch.basic_ack(delivery_tag=method.delivery_tag)

        p = get_pusher()    
        body = json.loads(body)

        event = body['event']
        channel = body['channel']
        data = body['data']

        logger.info("trigger")
        logger.info(data)
        try:
            p[channel].trigger(event, data)
        except Exception, e:
            now=datetime.now()
            p[channel].trigger(event, data = {'datetime': str(now), 'message': str(e), 'class': "error"})
            logger.error("Cannot send data to pusher")
            logger.exception(e)
        logger.info("pusher event sent")
        #logger.info("ack start")
        #ch.basic_ack(delivery_tag = method.delivery_tag)
        #logger.info("ack done")