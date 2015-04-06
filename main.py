import pprint
from twython import Twython
from twython.exceptions import TwythonRateLimitError
from twython import TwythonError
from dateutil.parser import parse
import datetime
import pymongo
import sys
import time
from urllib2 import Request, urlopen, URLError
from urllib import urlencode
from config import *
ppr = pprint.PrettyPrinter()


#For pushing notifications to boxcar api
def push_not(title, message):
    url = 'https://new.boxcar.io/api/notifications'
    values = {'user_credentials' : BOXCAR_KEY,
          'notification[title]' : title,
        'notification[sound]': 'echo',
         'notification[long_message]': message}
    data = urlencode(values)
    req = Request(url, data)
    response = urlopen(req)
    return response.read()

#For printing on the same line
def print_line(t):
    sys.stdout.write('\r' + t)
    sys.stdout.flush()

class Reporter:
    movie = status = collected = total = remaining = False
    def report(self, movie=False, status=False, collected=False, remaining=False):
        if movie != self.movie and movie:
            self.movie = movie
            self.collected = 0
        if status:
            self.status = status
        if collected:
            self.collected += collected
            self.total += collected
        if remaining:
            self.remaining = str(remaining)
        print_line(("Movie: " + self.movie + "; " if self.movie else '') + ("Status: " + self.status + "; " if self.status else '') + ("tweets collected for this movie: " + str(self.collected) + '; total: ' + str(self.total) + '; ' if self.collected else '') + ("requests remaining: " + self.remaining + '; ' if self.remaining else ''))

rep = Reporter()


#twitter.get_application_rate_limit_status(resources = ['search'])

def setup():
    twitter = Twython(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    twitter.verify_credentials()
    conn = pymongo.Connection()
    db = conn.tweets
    return db, twitter


#recents = api.GetSearch(term='#'+movie,result_type='recent', lang='en')



class rate_limiter:
    def __init__(self, twitter):
        self.twitter = twitter
        self.reset = int(time.time()) + 900 #Moment when reset will happen (actual value set with succesful request). Defaults to time + 15mins
    def handle(self):
        while True:
            try:
                status = self.twitter.get_application_rate_limit_status(resources = ['search'])['resources']['search']['/search/tweets']
                remaining = status['remaining']
                self.reset = int(status['reset'])
            except TwythonRateLimitError:
                remaining = 0
            except TwythonError:
                print "Non-rate-limit exception."
                remaining = 0
            if remaining > 0:
                #print str(remaining) + " available requests left"
                rep.report(status="Got request limit", remaining=remaining)
                return
            else:
                wait = max(self.reset - int(time.time()), 0) + 5
                #print "Asked to much from the API, waiting " + str(wait) + " seconds."
                rep.report(status="Reached limit " + str(wait) + " seconds.")
                time.sleep(wait)

#Modifies and saves tweets
def handle_tweets(dest,tweets, daysBack):
    minDate = datetime.datetime.now() - datetime.timedelta(days=daysBack)
    first = True
    for t in tweets:
        d = parse(t['created_at']).replace(tzinfo=None)
        if d > minDate:
            t['_id'] = t.pop('id') #change key from id to _id
            dest.insert(t)
            first = False
        else: #Tweet is too old
            if first: # We already processed of tweet of this list, give nothing useful back
                return 0, False
            else: #Give back the first tweet
                return tweets[0]['_id'], False
    return tweets[0]['_id'], tweets[-1]['_id'] #Return the highest id and id of last tweet fetched

def fetch_tweets(db, twitter, search_term, dest_coll, daysBack):
    rep.report(movie=dest_coll, status='Initialising...')
    since_id_orig = None
    since_id = None
    try:
        latest_tweet = db[dest_coll].find(limit=1, sort=[('_id',-1)])[0]
        since_id_orig = latest_tweet['_id']
        since_id = since_id_orig
        #print "Database was populated. Searching until last tweet in database or " + str(daysBack) + " days back."
        rep.report(status="Database was populated. Searching until last tweet in database or " + str(daysBack) + " days back.")
    except:
        #print "Collection isn't populated yet, fetching tweets from the last " + str(daysBack) + " days."
        rep.report(status="Collection isn't populated yet, fetching tweets from the last " + str(daysBack) + " days.")
    first_id = None
    first = None
    max_id = None #Used to go through 'pages' of tweets
    #noTweets_waitTime = 0
    #nit rate_limiter
    rl = rate_limiter(twitter)
    while True:
        rl.handle()
        recents = twitter.search(q=search_term, lang='en', result_type='recent', max_id=max_id, since_id=since_id, count=100)['statuses']
        if recents:
            #noTweets_waitTime = 0
            first, last = handle_tweets(db[dest_coll], recents, daysBack)
            #print "Found " + str(len(recents)) + " tweets: ids " + str(first) + " -> " + str(last)
            rep.report(status="Found tweets", collected=len(recents))
            max_id = last - 1 #We don't want the tweets that we already got (last would be included if we wouldn't do -1)
            first_id = first if not first_id else first_id #Remember the first tweet of this "round"
            if not(last): #We shouldn't continue going back in time
                #print "Done going back in time. Searching for new tweets"
                rep.report(status="Done going back in time. Searching for new tweets")
                max_id = None
                since_id = first_id if first_id else since_id_orig
        else: #No tweets found
            max_id = None
            since_id = first_id if first_id else since_id_orig
            #noTweets_waitTime += 1 #Wait 1 second longer
            #print "Found no tweets, waiting " + str(noTweets_waitTime) + " seconds"
            #time.sleep(noTweets_waitTime)
            rep.report(status="No new tweets")
            return


def main(argv=None):
    if (len(argv) < 2):
        print "Invalid arguments. Given: " + " ".join(argv)
        print "Valid format: python " + argv[0] + " daysBack"
        return
    try:
        db, twitter = setup()
    except KeyboardInterrupt:
        print "Shutting down"
    except Exception as e:
        print 'Error setting up: ' + str(e)
        return
    else:
        print "Setting up done"
    total_report = "Stats:"
    for t in collect_sources:
        fetch_tweets(db, twitter, t[0], t[1], int(argv[1])) #int() because everything gotten from argv is a string
        total_report += "\n" + t[1] + ": " + str(rep.collected)
    total_report += "\nTotal: " + str(rep.total)
    push_not(str(rep.total) + " tweets collected!", total_report)



if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        print "Shutting down"