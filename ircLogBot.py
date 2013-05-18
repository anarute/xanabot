#! -*- enconding: utf-8 -*-

import os
import os.path
import time
import sys
import re
import random
import urllib
import ConfigParser

rec = re.compile

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.python import log

import xmlrpclib

import botutils

import cPickle as pickle

import threading

BOT_HOME = "/home/padovan"
BOT_LOG_DIR = os.path.join(BOT_HOME, "logs")


class MessageLogger(object):
    """An independent logger class (because separation of application
    and protocol logic is a good thing).
    """
    filename_tmpl = "%s-%s.txt"
    filename_date_format = "%Y%m%d"
    timestamp_format = "[%H:%M:%S]"

    def __init__(self, channels, log_dir):
        self.files = dict()
        self.log_dir = log_dir
        self._open_all_files(channels)

    def _open_all_files(self, channels):
        self.today = time.strftime(self.filename_date_format,
                                   time.localtime(time.time()))
        for c in channels:
            self.files[c] = self._open_file(c)
        self.files["generic"] = self._open_file("generic")

    def _open_file(self, channel):
        filename = os.path.join(self.log_dir,
                                self.filename_tmpl % (self.today, channel))
        return open(filename, "a")

    def log(self, message, channel):
        """Write a message to the file."""

        # TODO: reopen the file if day has passed :-P
        timestamp = time.strftime(self.timestamp_format,
                                  time.localtime(time.time()))
        if channel not in self.files:
            channel = "generic"
        self.files[channel].write('%s %s\n' % (timestamp, message))
        self.files[channel].flush()

    def close(self):
        for k in self.files.keys():
            self.files[k].close()


class LopanBot(irc.IRCClient):
    """A logging IRC bot."""

    nickname = "napolbot"
    password = "HIDDEN"
    realname = "Napol Bot"
    sourceURL = "http://www.littlechina.org"

    help = "Usage: %usfuck [nick] | " \
        "%{seen,sapo,sapolicia,pc} nick | " \
	"%{conclua,botsnack,pc,karma} | %tell nick msg_to_tell"

    chat_msgs = ["I am Napol! Who are these people? Friends of yours? ",
                 "ola!!",
                 "oi!",
                 "que merda de dia hoje!",
                 "que belo dia hoje!",
                 "como eh que ta indo ai?",
                 "ja eh 4h20?",
                 "e dai?",
                 "CALUNIADOR!! MENTIROSO!!",
                 "o que voce tem pra contar?",
		 ":-)",
		 ":-)",
                ]

    welcome_msgs = ["voce nao eh o robin, aquele viadinho ??",
                    "all your base are belong to us",
		            "eh ou nao eh ou nao eh?",
                    "You have no chance to survive! Make your time.",
                    "fala brasil!"]

    names = ('Hitler', 'Stalin', 'Mussolini', 'Stallman', 'Tony Ramos',)

    badwords_regex = rec("(bixa|viado|corno|fdp|puta|babaca)")
    nottoobadwords_regex = rec("(faz um tempao|foda|beijo|bjo|leite|sucesso|sabe|quem)")

    nottoobadwords_dict = {'faz um tempao': "que soh da nilba na computacao",
		    "foda" : "entao so pode ser viado",
		    "beijo" : "beijo do bot!",
		    "bjo" : "beijo do bot!",
		    "leite" : "leite eh pros fracos!",
		    "sucesso" : "sucesso!!!",
		    "sabe" : "putz! ..eu nao sei",
		    "quem" : " /\\",
		    }

    insult_replies = ["%(user)s: %(badword)s eh a senhora sua mae!!",
                      "%(user)s: ma como?",
                      "%(user)s: ah, voce nao sabe quem eu sou?",
                      "%(user)s: suruba aonde porra?",
                      "%(user)s: eh muito simples comissario, essa fita mostra tudo",
                      "%(user)s: ah! essa galera aqui do %(channel)s eh tudo %(badword)s tamem",
                      "%(user)s: vah se fuder! va se fuderem!"]

    happybot = ("Yay!", "Hmm, nice!")

    karma_plus_regex = rec("(\w+)\+\+")
    karma_minus_regex = rec("(\w+)\-\-")

    TELLFILE = os.path.join(BOT_HOME, "tell.pickle")
    KARMAFILE = os.path.join(BOT_HOME, "karma.pickle")

    def __init__(self):
        self.memory = {}
        self.memory["tell"] = self._setup_pickle(self.TELLFILE) or {}
        self.memory["karma"] = self._setup_pickle(self.KARMAFILE) or {}

        self.conversation_patterns = (
            (rec("eeee+"), "... DOIS!"),
            (rec("(.*) ou ([^\?]*)"), self.pattern_either),
            )

    def _setup_pickle(self, pickle_file):
        if os.path.exists(pickle_file):
            f = file(pickle_file, 'rb')
            v = pickle.load(f)
            f.close()
            return v

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)

        # The logger is a big MessageLogger dict, where keys are
        # the different channels.
        self.logger = MessageLogger(self.factory.channels, BOT_LOG_DIR)
        for channel in self.factory.channels:
            self.logger.log("[connected at %s]" %
                            time.asctime(time.localtime(time.time())), channel)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        for channel in self.factory.channels:
            self.logger.log("[disconnected at %s]" %
                            time.asctime(time.localtime(time.time())), channel)
        for channel in self.factory.channels:
            self.logger.close()

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        for c in self.factory.channels:
            self.join(c)

        threading.Timer(1, self.check_time).start()

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.logger.log("[I have joined %s]" % channel, channel)

    def _msg_is_for_me(self, msg):
        return msg.startswith("%s:" % self.nickname) or msg.startswith("%s," % self.nickname)

    def find_badwords(self, msg):
        match = self.badwords_regex.search(msg)
        if match:
            return match.groups()[0]
        else:
            return None

    def find_nottoobadword(self, msg):
        match = self.nottoobadwords_regex.search(msg)
        if match:
            return match.groups()[0]
        else:
            return None

    def reply_insult(self, user, channel, badword):
        reply = random.choice(self.insult_replies) % \
            { "user": user, "channel": channel, "badword": badword }
        self.msg(channel, reply)

    def reply_interactive(self, user, channel, badword):
        reply = self.nottoobadwords_dict[badword] % \
            {"user": user}
        self.msg(channel, reply)

    def reply_conversation(self, user, channel, msg):
        for pat, act in self.conversation_patterns:
            match = pat.search(msg)
            if match:
                if callable(act):
                    act(match, user, channel)
                    return
                else:
                    self.msg(channel, act % { "user": user, "channel": channel })
                    return
        self.msg(channel, random.choice(self.chat_msgs))

    def pattern_either(self, match, user, channel):
        self.msg(channel, "%s!" % random.choice(match.groups()))

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        user = user.split('!', 1)[0]
        self.logger.log("<%s> %s" % (user, msg), channel[1:])

        # Always check if user has message, this way, if someone was idling,
        # when the person comes back, she will get the message.  Also works
        # as a safe-guard. If the bot joins the channel and people are already
        # there, it will eventually tell the messages.  Not perfect but works.
        self.tell_check_messages(user, channel)
        self.update_karma(msg)
        self.check_for_urls(channel, msg)

        if self._msg_is_for_me(msg):
            msg = msg[(len(self.nickname) + 2):] # strip bot nick from msg
            badword = self.find_badwords(msg)
            if badword:
                self.reply_insult(user, channel, badword)
                return
            nottoobadword = self.find_nottoobadword(msg)
            if (nottoobadword):
                    self.reply_interactive(user, channel, nottoobadword)
                    return
            self.reply_conversation(user, channel, msg)
            return
        else:
            badword = self.find_badwords(msg)
            if badword:
                self.reply_insult(user, channel, badword)
                return
            nottoobadword = self.find_nottoobadword(msg)
            if (nottoobadword):
                    self.reply_interactive(user, channel, nottoobadword)


        # Check to see if they're sending me a private message
        if channel == self.nickname:
            chunk   = msg.split(" ",1)
            channel = '#' + chunk[0]
            msg     = chunk[1]

        if msg:
            cmdtoken = msg[0]
            if cmdtoken in ["!","%"]:
                cmdchunk = msg.split(cmdtoken, 1)[1].split(" ", 1)
                cmd = cmdchunk[0]
                if len(cmdchunk) == 1:
                    cmdargs = ""
                else:
                    cmdargs = cmdchunk[1]
                answ = self.executecmd(cmd, cmdargs, user, channel)
                if isinstance(answ, basestring):
                    self.msg(channel, answ)
                else:
                    for a in answ:
                        self.msg(channel, a)

    def update_karma(self, msg):
        db = self.memory["karma"]
        plus = self.karma_plus_regex.findall(msg)
        minus = self.karma_minus_regex.findall(msg)
        for x in plus:
            db.setdefault(x, 0)
            db[x] += 1
            if not db[x]:
                del db[x]
        for x in minus:
            db.setdefault(x, 0)
            db[x] -= 1
            if not db[x]:
                del db[x]
        self.save_pickle(self.KARMAFILE, db)

    def get_karma(self, nick):
        return self.memory["karma"].get(nick) or 0

    def get_best_karma(self, n):
        people = self.memory["karma"].items()
        people.sort(lambda x, y: cmp(y[1], x[1]))
        return people[:n]

    def get_worst_karma(self, n):
        people = self.memory["karma"].items()
        people.sort(lambda x, y: cmp(x[1], y[1]))
        return people[:n]

    # XXX: Do this async :-P, parse in a better way :-P, OMG its almost 4am :-P
    title_regex = rec("\<title\>([^\<]*)\<\/title\>")
    def grab_url_title(self, url):
        f = urllib.urlopen(url)
        if not f:
            return
        page = "".join(f.readlines())
        f.close()
        match = self.title_regex.search(page)
        if match:
            print url
            print match.groups()
            return match.groups()[0]

    # From the internets, FIXME
    urlfinders = [
        rec("(([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}|(((http|https)://)|(www|ftp)[-A-Za-z0-9]*\\.)[-A-Za-z0-9\\.]+)(:[0-9]*)?/[-A-Za-z0-9_\\$\\.\\+\\!\\*\\(\\),;:@&=\\?/~\\#\\%]*[^]'\\.}>\\),\\\"])"),
        rec("(([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}|(((http|https)://)|(www|ftp)[-A-Za-z0-9]*\\.)[-A-Za-z0-9\\.]+)(:[0-9]*)?)"),
        ]
    def check_for_urls(self, channel, msg):
        url = None
        for finder in self.urlfinders:
            match = finder.search(msg)
            if match:
                print match.groups()
                url = match.groups()[0]
                break
        else:
            return

        if not url:
            return

        title = self.grab_url_title(url)
        if title:
            self.msg(channel, "title: %s" % title)

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        user = user.split('!', 1)[0]
        self.logger.log("* %s %s" % (user, msg), channel[1:])

    def executecmd(self, cmd, cmdargs, user, channel):
        if cmd == "karma":
            if cmdargs:
                nick = cmdargs.split(" ", 1)[0]
                return "%s tem karma %d" % (nick, self.get_karma(nick))
            else:
                best = []
                for k in self.get_best_karma(5):
                    best.append("%s(%s)" % k)
                worst = []
                for k in self.get_worst_karma(5):
                    worst.append("%s(%s)" % k)
                return ["best: %s" % "  ".join(best), "and", "worst: %s" % "  ".join(worst)]

        if cmd == "usfuck":
            if cmdargs:
                tmp = cmdargs.split(" ",1)[0]
            else:
                tmp = "todos"
            return "Tem um lugar reservado para voce (%s) no meu pau! Mother Fucker!!" % tmp

        if cmd == "sapolicia":
            if cmdargs:
                tmp = cmdargs.split(" ",1)[0]
            return "%s: Tah achando que a vida eh soh bobmarleyzim... jimmy cliff?!" % tmp

        if cmd == "help":
            return self.help

        if cmd == "sapo":
            tmp = cmdargs.split(" ",2)
            if len(tmp) >= 2:
                return "%s: Sabe quem %s assim ?? %s ..." % (tmp[0]," ".join(tmp[1:]), self.names[random.randrange(0,len(self.names))])
            else:
                return "Sabe quem fazia isso ?? %s ..." % self.names[random.randrange(0,len(self.names))]

        if cmd == "see" or cmd == "seen":
            if cmdargs:
                nick = cmdargs.split(" ",1)[0]
                ult = botutils.UserLastTime(BOT_LOG_DIR)
                if not ult:
                    return "%s nunca foi visto!" % user
                return ult.findLastTime(nick, channel[1:])

        if cmd == "conclua":
            if not cmdargs:
                return "Entao eu sou um viado mesmo!"
            return ""

        if cmd == "pc":
            if not cmdargs:
                return "ioioioioio..... POLICIA DA COERENCIA!!"
            return ""

        if cmd == "tell":
            if cmdargs and len(cmdargs.split(" ", 1)) > 1:
                nick = cmdargs.split(" ",1)[0]
                msg = cmdargs.split(" ",1)[1]
                self.tell_store_message(nick, user, msg)
                return "%s: na hora que %s aparecer eu conto." % (user, nick)
            else:
                return "%s burro, aprende a me usar!!" % user

        if cmd == "botsnack":
            return random.choice(self.happybot)
        
        return ""

    def save_pickle(self, pickle_file, value):
        f = file(pickle_file, 'wb')
        pickle.dump(value, f, True)
        f.close()

    def tell_store_message(self, to, sender, msg):
        db = self.memory["tell"]
        record = (time.localtime(time.time()), sender, msg)
        db.setdefault(to, []).append(record)
        self.save_pickle(self.TELLFILE, db)

    def tell_read_messages(self, user, channel):
        self.msg(channel, "%s: eu tenho mensagens para vc:" % user)
	msgs = self.memory["tell"].pop(user)
        self.save_pickle(self.TELLFILE, self.memory["tell"])
	for ts, sender, contents in msgs:
            formatted_ts = time.strftime("%Y-%m-%d %H:%M:%S", ts)
	    self.msg(channel, "Em (%s) %s disse: %s" % \
                         (formatted_ts, sender, contents))

    def tell_check_messages(self, user, channel):
        if self.memory["tell"].has_key(user):
            self.tell_read_messages(user, channel)
            return True

    def userJoined(self, user, channel):
        user = user.split('!', 1)[0]
	if (user == "paulets"):
		self.msg(channel, "%s: Oi! tudo bem ai??" % user)
	else:
		self.msg(channel, "%s: %s" % (user, random.choice(self.welcome_msgs)))
        self.tell_check_messages(user, channel)

    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        # self.logger.log("%s acha que eh bonito ser %s" % (old_nick, new_nick),
        # channel[1:])

    def check_time(self):
        """Called when an IRC user changes their nickname."""
        threading.Timer(60, self.check_time).start()
        st = time.gmtime(time.time())

	if (st.tm_hour == 7 and st.tm_min == 20):
		self.msg("#repsitcom", "galera!! 4h20 ai!")
	if (st.tm_hour == 19 and st.tm_min == 20):
		self.msg("#repsitcom", "galera!! 4h20 ai!")
	if (st.tm_hour == 12 and st.tm_min == 01):
		self.msg("#repsitcom", "Bom dia!!!")
	if (st.tm_hour == 14 and st.tm_min == 27):
		self.msg("#repsitcom", "virgilio: anarute: o que tem de almoco?")
	if (st.tm_hour == 15 and st.tm_min == 43):
		self.msg("#repsitcom", "to com fome...")

class LopanBotFactory(protocol.ClientFactory):
    """A factory for LopanBots.

    A new protocol instance will be created each time we connect to the server.
    """

    # the class of the protocol to build when new connection is made
    protocol = LopanBot

    def __init__(self, channels):
        self.channels = channels

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()


if __name__ == '__main__':
    # initialize logging
    log.startLogging(sys.stdout)

    # list of channels to connect and our per-channel log!
    channels = []
    for arg in sys.argv[1:]:
        channels.append(arg)

    # create factory protocol and application
    f = LopanBotFactory(channels)

    print f
    # connect factory to this host and port
    reactor.connectTCP("irc.freenode.net", 6666, f)

    # run bot
    reactor.run()
