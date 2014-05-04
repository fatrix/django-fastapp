import pika
import uuid
import json
import copy
import logging
import threading
import traceback
import time
from bunch import Bunch
from django.core import serializers
from fastapp.utils import connect_to_queuemanager
#from fastapp.models import Apy

logger = logging.getLogger(__name__)

def distribute(event, apy, vhost, username, password):

    class ExecutorClient(object):
        """
        Gets the apy (id, name, module) and sets them on the _do function.__add__ .
        Then the client is ready to response for execution requests.

        """
        def __init__(self, vhost, username, password):
            # get needed stuff
            self.connection = connect_to_queuemanager(
                vhost=vhost,
                username=username,
                password=password
                )

            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange=event, type='fanout')


        def call(self, body):
            self.channel.basic_publish(exchange=event,
                                       routing_key='',
                                       body=body)

            self.connection.close()

    executor = ExecutorClient(vhost, username, password)
    executor.call(apy)

    return  True

def call_rpc_client(apy, vhost, username, password):

    class ExecutorClient(object):
        """
        Gets the apy (id, name, module) and sets them on the _do function.__add__ .
        Then the client is ready to response for execution requests.

        """
        def __init__(self, vhost, username, password):
            # get needed stuff
            self.connection = connect_to_queuemanager(
                vhost=vhost,
                username=username,
                password=password
                )


            self.channel = self.connection.channel()

            result = self.channel.queue_declare(exclusive=True)
            self.callback_queue = result.method.queue

            self.channel.basic_consume(self.on_response, no_ack=True,
                                       queue=self.callback_queue)


        #def _get_base():
        #    apys = requests.get("http://localhost:8000/fastapp/api/base/23/apy/")
        def on_timeout(self):
            logger.error("timeout in waiting for response")
            #return {u'status': u'TIMEOUT', u'exception': None, u'returned': None, 'id': u'cannot_import'}
            raise Exception("Timeout")

        def on_response(self, ch, method, props, body):
            if self.corr_id == props.correlation_id:
                self.response = body
                #print int(round(time.time() * 1000))

        def call(self, n):
            self.connection.add_timeout(3, self.on_timeout)
            self.response = None
            self.corr_id = str(uuid.uuid4())
            self.channel.basic_publish(exchange='',
                                       routing_key='rpc_queue',
                                       properties=pika.BasicProperties(
                                             reply_to = self.callback_queue,
                                             delivery_mode=1,
                                             correlation_id = self.corr_id,
                                             ),
                                       body=str(n))
            while self.response is None:
                self.connection.process_data_events()
            return self.response

    executor = ExecutorClient(vhost, username, password)

    try:
        response = executor.call(apy)
    except Exception, e:
        response = json.dumps({u'status': u'TIMEOUT', u'exception': None, u'returned': None, 'id': u'cannot_import'})
    return response


STATE_OK = "OK"
STATE_NOK = "NOK"
STATE_NOT_FOUND = "NOT_FOUND"

threads = []

CONFIGURATION_QUEUE = "configuration"
SETTING_QUEUE = "setting"
RPC_QUEUE = "rpc_queue"
HEARTBEAT_QUEUE = "heartbeat_queue"

class ExecutorServerThread(threading.Thread):
    def __init__(self, threadID, name, counter, vhost, username, password):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter

        # adds
        self.vhost = vhost
        self.username = username
        self.password = password

        # container for functions
        self.functions = {}
        # container for settings
        self.settings = {}

    def run(self):
        print "Starting " + self.name
        self.listen()

    def listen(self):
        # open connection and channel
        try:
            connection = connect_to_queuemanager(
                    vhost=self.vhost,
                    username=self.username,
                    password=self.password
                    )
            channel = connection.channel()


            # listen for configuration events on topic configuration
            # configuration are:
            #    - settings
            #    - apys
            # configuration
            channel.exchange_declare(exchange=CONFIGURATION_QUEUE, type='fanout')
            result = channel.queue_declare(exclusive=True)
            self.queue_name = result.method.queue
            channel.queue_bind(exchange=CONFIGURATION_QUEUE, queue=self.queue_name)
            # setting
            channel.exchange_declare(exchange=SETTING_QUEUE, type='fanout')
            result = channel.queue_declare(exclusive=True)
            self.setting_queue_name = result.method.queue
            channel.queue_bind(exchange=SETTING_QUEUE, queue=self.setting_queue_name)

            # listen for rpc events
            channel.queue_declare(queue=RPC_QUEUE)

            def on_configuration_request(ch, method, props, body):
                fields = json.loads(body)[0]['fields']
                #exec fields['module'] in globals(), locals()
                #exec fields['module'] in globals(), globals()
                #exec fields['module'] in globals(), locals()
                try:
                    exec fields['module'] in globals(), locals()
                    self.functions.update({
                        fields['name']: func,
                        })
                    logger.info("Configuration '%s' received in %s" % (fields['name'], self.name))
                except Exception, e:
                    logger.exception(e)

            def on_setting_request(ch, method, props, body):
                json_body = json.loads(body)
                key = json_body.keys()[0]
                #fields = json.loads(body)[0]['fields']
                self.settings.update(json_body)
                logger.info("Setting '%s' received in %s" % (key, self.name))

            def on_rpc_request(ch, method, props, body):
                logger.info("Request received in %s" % self.name)
                try:
                    response_data = {}
                    response_data = _do(json.loads(body), self.functions, self.settings)

                except Exception, e:
                    print e
                finally:
                    ch.basic_publish(exchange='',
                                     routing_key=props.reply_to,
                                     properties=pika.BasicProperties(
                                        correlation_id = props.correlation_id,
                                        delivery_mode=1,
                                        ),
                                     body=json.dumps(response_data))
                    ch.basic_ack(delivery_tag = method.delivery_tag)

            channel.basic_qos(prefetch_count=3)
            channel.basic_consume(on_rpc_request, queue=RPC_QUEUE)
            channel.basic_consume(on_configuration_request, queue=self.queue_name, no_ack=True)
            channel.basic_consume(on_setting_request, queue=self.setting_queue_name, no_ack=True)

            logger.info("Waiting for events")
            channel.start_consuming()
        except Exception, e:
            logger.error("Connection closed")
            logger.exception(e)

class HeartbeatThread(threading.Thread):

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
        print "Starting " + self.name

        if self.receiver:
            self.on_queue_declared = self.consume_on_queue_declared
        else:
            self.on_queue_declared = self.produce_on_queue_declared
        print self.on_queue_declared

        while True:
            try:
                connection = pika.SelectConnection(self.parameters, self.on_connected)
                logger.info('connected')
            except Exception:
                logger.warning('cannot connect', exc_info=True)
                time.sleep(10)
                continue

            try:
                connection.ioloop.start()
            finally:
                try:
                    connection.close()
                    connection.ioloop.start() # allow connection to close
                except Exception, e:
                    logger.error("Heartbeat thread lost connection")
                    logger.exception(e)

    def consume_on_queue_declared(self, frame):
        logger.info("consume on queue declared")
        self.channel.basic_consume(self.on_beat, queue=HEARTBEAT_QUEUE, no_ack=True)

    def produce_on_queue_declared(self, frame):
        logger.info("produce on queue declared")
        while True:
            logger.info("Sending Heartbeat from %s" % self.vhost)
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
            time.sleep(10)

    def on_connected(self, connection):
        print "on connected"
        connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        print "on channel open"
        channel.queue_declare(queue=HEARTBEAT_QUEUE, callback=self.on_queue_declared)

        self.channel = channel

    def on_beat(self, ch, method, props, body):
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
        #ch.basic_ack(delivery_tag=method.delivery_tag)
        #logger.info("ack")



class ApyNotFound(Exception):
    pass

class ApyError(Exception):
    pass




def _do(data, functions=None, settings=None):
        exception = None;  returned = None
        status = STATE_OK

        request = Bunch(data['request'])
        base_name = data['base_name']
        model = json.loads(data['model'])

        # worker does not know apy
        if not functions.has_key(model['fields']['name']):
            status = STATE_NOT_FOUND
        # go ahead
        else:
            func = functions[model['fields']['name']]
            #print "REQUEST ARRIVED"
            session = request['session']
            logger.info("do %s" % request)
            username = copy.copy(request['user']['username'])

            # debug incoming request
            if request['method'] == "GET":
                query_string = copy.copy(request['GET'])
            else:
                query_string = copy.copy(request['POST'])
            #try:
            #    query_string.pop('json')
            #except KeyError, e:
            #    logger.exception("invalid request")
            response_class = None
            try:

                #exec model['fields']['module']
                func.username=username
                func.request=request
                func.session=session

                func.name = model['fields']['name']

                # attach GET and POST data
                func.GET=copy.deepcopy(request['GET'])
                func.POST=copy.deepcopy(request['POST'])

                # attach Responses classes
                from fastapp import responses
                func.responses = responses

                # attach log functions
                #func.info=info
                #func.debug=debug
                #func.warn=warn
                #func.error=error

                # attatch settings
                setting_dict = settings
                setting_dict1 = Bunch()
                for key, value in setting_dict.iteritems():
                    setting_dict1.update({key: value})
                setting_dict1.update({'STATIC_DIR': "/%s/%s/static" % ("fastapp", base_name)})
                func.settings = setting_dict1

                # execution
                returned = func(func)
                if isinstance(returned, responses.Response):
                    # serialize 
                    response_class = returned.__class__.__name__
                    returned = str(returned)


            except Exception, e:
                exception = "%s: %s" % (type(e).__name__, e.message)
                traceback.print_exc()
                status = STATE_NOK
        return_data = {"status": status, "returned": returned, "exception": exception, "response_class": response_class}
        return return_data