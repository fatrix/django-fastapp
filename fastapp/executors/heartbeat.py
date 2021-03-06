import pika
import logging
import time
import json
import sys
from datetime import datetime, timedelta

from django.core import serializers
from django.conf import settings
from fastapp.executors.remote import distribute
from fastapp.models import Executor, Instance, Process, Thread
from fastapp.queue import CommunicationThread

logger = logging.getLogger(__name__)

HEARTBEAT_QUEUE = "heartbeat_queue"
CONFIGURATION_QUEUE = "configuration"
SETTING_QUEUE = "setting"


def inactivate():
    try:
        while True:
            time.sleep(0.1)
            now=datetime.now()
            for instance in Instance.objects.filter(last_beat__lte=now-timedelta(minutes=1), is_alive=True):
                logger.info("inactive instance '%s' detected" % instance)
                instance.mark_down()
                instance.save()

            # start if is_started and not running    
            for executor in Executor.objects.filter(started=True):
                if not executor.is_running():
                    # log start with last beat datetime
                    executor.start()
            time.sleep(10)
    except Exception, e:
        logger.exception(e)

def update_status(parent_name, thread_count, threads):
    try:
        while True:
            time.sleep(0.1)
            alive_thread_count = 0
            process , created = Process.objects.get_or_create(name=parent_name)

            # threads
            for t in threads:
                logger.debug(t.name+": "+str(t.isAlive()))

                # store in db
                thread_model, created = Thread.objects.get_or_create(name=t.name, parent=process)
                if t.isAlive() and t.health():
                    logger.info("Thread '%s' is healthy." % t.name)
                    thread_model.started()
                    alive_thread_count=alive_thread_count+1
                else:
                    logger.warn("Thread '%s' is not healthy." % t.name)
                    thread_model.not_connected()
                thread_model.save()

            # process functionality
            if thread_count == alive_thread_count:
                process.up()
                process.save()
                logger.info("Process is healthy.")
            else:
                logger.error("Process is not healthy. Threads: %s / %s" % (alive_thread_count, thread_count))
            time.sleep(10)

    except Exception, e:
        logger.exception(e)



class HeartbeatThread(CommunicationThread):


    def send_message(self):
        logger.info("send message to vhost: %s:%s" % (self.vhost, HEARTBEAT_QUEUE))
        payload = {'in_sync': self.in_sync}
        payload.update(self.additional_payload)
        self.channel.basic_publish(exchange='',
                routing_key=HEARTBEAT_QUEUE,
                properties=pika.BasicProperties(
                    #delivery_mode=1,
                    #reply_to = self.callback_queue,
                    #correlation_id = self.corr_id,
                ),
                body=json.dumps(payload)
            )
        self.in_sync = True
        self.schedule_next_message()

    def on_message(self, ch, method, props, body):
        try:
            logger.debug(self.name+": "+sys._getframe().f_code.co_name)
            data = json.loads(body)
            vhost = data['vhost']
            base = vhost.split("-")[1]

            logger.info("Heartbeat received from '%s'" % vhost)

            # store timestamp in DB
            from fastapp.models import Instance
            instance = Instance.objects.get(executor__base__name=base)
            instance.is_alive = True
            instance.last_beat = datetime.now()
            instance.save()

            if not data['in_sync']:
                logger.info("Run sync to vhost: "+vhost)
                from fastapp.models import Apy, Setting
                for instance in Apy.objects.filter(base__name=base):
                    distribute(CONFIGURATION_QUEUE, serializers.serialize("json", [instance,]), 
                        #"philipsahli-aaaa", 
                        vhost,
                        instance.base.name,
                        instance.base.executor.password
                        )

                for instance in Setting.objects.filter(base__name=base):
                    distribute(SETTING_QUEUE, json.dumps({
                        instance.key: instance.value
                        }), 
                        vhost,
                        instance.base.name,
                        instance.base.executor.password
                    )
        except Exception, e:
            logger.exception(e)
        time.sleep(0.1)        



    def schedule_next_message(self):
        #logger.info('Next beat in %0.1f seconds',
                    #self.PUBLISH_INTERVAL)
        self._connection.add_timeout(settings.FASTAPP_PUBLISH_INTERVAL,
                                     self.send_message)
