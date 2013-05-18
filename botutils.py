import os
import os.path
import random
import time
import re

class UserLastTime(object):
    def __init__(self, log_dir):
        self.log_dir = log_dir

    def findLastTime(self, username, channel):
        # look from this day and backward
        t = time.strftime("%Y %m %d", time.localtime(time.time()))
        [y, m, d] = t.split(" ", 3)
        mon = int(m)
        day = int(d)
        yer = int(y)
        while yer > 2007:
            while mon > 04:
                while day >= 01:
                    syear = str(yer)
                    smon  = str(mon).rjust(2,"0")
                    sday  = str(day).rjust(2,"0")
                    # XXX: maybe joining this with the Logger is a good idea,
                    # if not, we need to get the rules for log naming from the
                    # same place.
                    filename = "%s%s%s-%s.txt" % (syear, smon, sday, channel)
                    logname = os.path.join(self.log_dir, filename)
                    if os.path.exists(logname):
                        msg = self.findFile(logname, username)
                        if msg:
                            msgline = "%s-%s-%s %s" % (syear, smon, sday, msg)
                            return msgline
                    day -= 1
                mon -= 1
            yer -= 1
        return ""

    def findFile(self, logname, username):
        fd = open(logname, "r")
        lines = fd.readlines()
        fd.close()

        # find the man!!
        lines.reverse()
        r = re.compile("\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] \[[0-9]{2}:[0-9]{2}:[0-9]{2}\]<%s>" % username)
        for l in lines:
            if r.match(l):
                return l[11:-1]

        return ""
