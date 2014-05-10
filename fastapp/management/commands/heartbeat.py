import logging
import sys
import threading

from django.core.management.base import BaseCommand

from fastapp.executors.heartbeat import HeartbeatThread, inactivate, update_status
from fastapp.defaults import *

logger = logging.getLogger("fastapp.executors.remote")

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'


    def handle(self, *args, **options):
        THREAD_COUNT = FASTAPP_HEARTBEAT_LISTENER_THREADCOUNT
        threads = []

        inactivate_thread = threading.Thread(target=inactivate)
        inactivate_thread.daemon = True
        inactivate_thread.start()


        #for c in range(0, THREAD_COUNT):
        for c in range(0, 3):
            name = "HeartbeatThread-%s" % c
            thread = HeartbeatThread(c, name, c, None, receiver=True)
            self.stdout.write('Start HeartbeatThread')
            threads.append(thread)
            thread.daemon = True
            thread.start()

        update_status_thread = threading.Thread(target=update_status, args=[3, threads])
        update_status_thread.daemon = True
        update_status_thread.start()

        for t in threads:
            #print "join %s " % t
            try:
                logger.info("%s Thread started" % THREAD_COUNT)
                t.join(1000)
            except KeyboardInterrupt:
                print "Ctrl-c received."
                sys.exit(0)