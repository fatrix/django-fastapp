import threading
import pika
import logging
import time
import json
import sys

from django.core import serializers
from fastapp.executors.remote import distribute

logger = logging.getLogger(__name__)

HEARTBEAT_QUEUE = "heartbeat_queue"
CONFIGURATION_QUEUE = "configuration"
SETTING_QUEUE = "setting"



class HeartbeatThread(threading.Thread):
    PUBLISH_INTERVAL = 20

    def __init__(self, threadID, name, counter, vhost, receiver=False):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.receiver = receiver

        self.vhost = vhost

        self.in_sync = False

    def run(self):
        self.parameters = pika.ConnectionParameters(host="localhost", heartbeat_interval=3)
        logger.info("starting " + self.name)

        if self.receiver:
            self.on_queue_declared = self.consume_on_queue_declared
        else:
            self.on_queue_declared = self.produce_on_queue_declared
        print self.on_queue_declared

        self._run = True
        while self._run:
            try:
                self._connection = pika.SelectConnection(self.parameters, self.on_connected, on_close_callback=self.on_close)
                logger.info('connected')
            except Exception:
                logger.warning('cannot connect', exc_info=True)
                time.sleep(10)
                continue

            try:
                self._connection.ioloop.start()
            except KeyboardInterrupt:
                logger.info("interrupt1")
                self.stop()
            finally:
                pass
                logger.info("interrupt2")
                try:
                    logger.info("interrupt3")
                    self._connection.close()
                    self._connection.ioloop.start() # allow connection to close
                except Exception, e:
                    logger.error("Heartbeat thread lost connection")
                    logger.exception(e)

    def stop(self):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        """Stop the example by closing the channel and connection. We
        set a flag here so that we stop scheduling new messages to be
        published. The IOLoop is started because this method is
        invoked by the Try/Catch below when KeyboardInterrupt is caught.
        Starting the IOLoop again will allow the publisher to cleanly
        disconnect from RabbitMQ.

        """
        self._run = False
        logger.info('Stopping')
        self._stopping = True
        self.close_channel()
        self.close_connection()
        self._connection.ioloop.start()
        logger.info('Stopped')


    def on_close(self, connection, reply_code, reply_text):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)

    def consume_on_queue_declared(self, frame):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        self.channel.basic_consume(self.on_beat, queue=HEARTBEAT_QUEUE, no_ack=True)

    def produce_on_queue_declared(self, frame):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        logger.info("Sending Heartbeat from %s" % self.vhost)
        self.send_message()

    def on_connected(self, connection):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        self._connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        channel.queue_declare(queue=HEARTBEAT_QUEUE, callback=self.on_queue_declared)

        self.channel = channel

    def send_message(self):
        self.channel.basic_publish(exchange='',
                routing_key=HEARTBEAT_QUEUE,
                properties=pika.BasicProperties(
                    #delivery_mode=1,
                    #reply_to = self.callback_queue,
                    #correlation_id = self.corr_id,
                ),
                body=json.dumps({
                    'in_sync': self.in_sync,
                    'vhost': self.vhost 
                    }))
        self.in_sync = True
        self.schedule_next_message()

    def schedule_next_message(self):
        """If we are not closing our connection to RabbitMQ, schedule another
        message to be delivered in PUBLISH_INTERVAL seconds.

        """
        #if self._stopping:
        #    return
        logger.info('Next beat in %0.1f seconds',
                    self.PUBLISH_INTERVAL)
        self._connection.add_timeout(self.PUBLISH_INTERVAL,
                                     self.send_message)

    def on_beat(self, ch, method, props, body):
        logger.info(self.name+": "+sys._getframe().f_code.co_name)
        data = json.loads(body)
        vhost = data['vhost']
        base = vhost.split("-")[1]

        logger.info("heartbeat received from %s" % vhost)

        # store timestamp in DB
        from fastapp.models import Instance
        instance = Instance.objects.get(executor__base__name=base)
        instance.is_alive = True
        instance.save()

        if not data['in_sync']:
            logger.info("run sync")
            from fastapp.models import Apy, Setting
            for instance in Apy.objects.filter(base__name=base):
                distribute(CONFIGURATION_QUEUE, serializers.serialize("json", [instance,]), 
                    #"philipsahli-aaaa", 
                    vhost,
                    "philipsahli", 
                    "philipsahli"
                    )

            for instance in Setting.objects.filter(base__name=base):
                distribute(SETTING_QUEUE, json.dumps({
                    instance.key: instance.value
                    }), 
                    vhost,
                    "philipsahli", 
                    "philipsahli"
                )
        logger.info(self.name+": ack")
        time.sleep(0.1)
        #ch.basic_ack(delivery_tag=method.delivery_tag)
