from django.core.management.base import BaseCommand
import logging
import sys

from fastapp.executors.remote import HeartbeatThread
from fastapp.defaults import *

logger = logging.getLogger("fastapp.executors.remote")

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'


    def handle(self, *args, **options):
        THREAD_COUNT = FASTAPP_HEARTBEAT_LISTENER_THREADCOUNT
        threads = []
        for c in range(0, THREAD_COUNT):
                thread = HeartbeatThread(c, "HeartbeatThread-%s" % c, c, None, receiver=True)
                self.stdout.write('Start HeartbeatThread')
                threads.append(thread)
                thread.daemon = True
                thread.start()

        for t in threads:
            #print "join %s " % t
            try:
                logger.info("%s Thread started" % THREAD_COUNT)
                t.join(1000)
            except KeyboardInterrupt:
                print "Ctrl-c received."
                sys.exit(0)