import ssl
import logging
import sqlite3
import googlemaps
import time
from queue import Queue
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Unauthorized
from queue import Queue
from telegram import ReplyKeyboardRemove
from telegram import ReplyKeyboardMarkup
from threading import Thread
import urllib.error
import urllib.parse
import urllib.request
import flood_protection
from telegram import Bot,KeyboardButton,ForceReply,ChatAction
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler, MessageHandler,Updater,Filters,CallbackQueryHandler
from configparser import ConfigParser
import bs4 as bs

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
config = ConfigParser()
config.read('config.ini')
TOKEN = config.get('telegram','bot_token')
GOOGLE_MAP_KEY=config.get('google-geocode','api_key')
BOT_URL=config.get('telegram','bot_url')
adminlist=str(config.get('telegram','admin_chat_id')).split(',')
mount_point=config.get('openshift','persistent_mount_point')
gmaps = googlemaps.Client(key=GOOGLE_MAP_KEY)

conn = sqlite3.connect(mount_point+'hk_bot.db')
create_table_request_list = [
    'CREATE TABLE location(id TEXT PRIMARY KEY,country TEXT,city TEXT)',
    'CREATE TABLE subscribers(id TEXT PRIMARY KEY,country TEXT,city TEXT,coun1 int DEFAULT 0,cit1 int DEFAULT 0)',
]
for create_table_request in create_table_request_list:
    try:
        conn.execute(create_table_request)
    except:
        pass
conn.commit()
conn.close()

REC_LOC,UPCM_2,GH_LIST,GET_CITY,DB,BDC,GET_COUNTRY,UPCM_1,SET_LOC,SET_COUNTRY,SET_CITY,SUBS_2,UNSUB_1=range(13)

timeouts = flood_protection.Spam_settings()

# UTILITY FUNCTIONS ...............................................................................

# FUNCTION TO SEND UPCOMING HACKATHONS TO SUBSCRIBERS
sched = BackgroundScheduler()
@sched.scheduled_job('cron',day_of_week='sun')
def subs_sender():
    conn = sqlite3.connect(mount_point+'hk_bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM subscribers')
    for row in c.fetchall():
        a=row[0]
        country=row[1]
        city=row[2]
        coun1=row[3]
        cit1=row[4]
        if coun1 == 1:
            url = 'https://www.hackathon.com/country/' + country
            fetcher_for_subscriber(url=url,chat_id=a)
        elif cit1 == 1:
            url = 'https://www.hackathon.com/city/' + country + '/' + city
            fetcher_for_subscriber(url=url, chat_id=a)
        time.sleep(1)
sched.start()

# FUNCTION TO SCRAPE THE WEBSITE
def fetcher(url,bot,query):
    try:
        gcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        url1 = urllib.request.Request(url=url,
                                      headers={'Content-Type': 'application/json', 'User-agent': 'Mozilla/5.0'})
        rawData = urllib.request.urlopen(url=url1, context=gcontext).read().decode('utf-8')
        soup = bs.BeautifulSoup(rawData, 'html5lib')
        to_send = []
        index = 1
        for card_holder in soup.findAll('div', {"class": "small-12 medium-6 large-12 column"}):
            formatted_row = format_message_row(getRow(card_holder), index)
            to_send.append(formatted_row)
            index = index + 1
        if len(to_send) == 0:
            bot.edit_message_text(text="Sorry I could not find any hackathons", chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)
        else:
            paginate_and_send(bot, query, to_send)
    except:
        bot.edit_message_text(text="Sorry I could not find any hackathons", chat_id=query.message.chat_id,
                              message_id=query.message.message_id)


# SAME THING FOR SUBSCRIBERS
def fetcher_for_subscriber(url,chat_id):
    bot=Bot(TOKEN)
    try:
        gcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        url1 = urllib.request.Request(url=url,
                                      headers={'Content-Type': 'application/json', 'User-agent': 'Mozilla/5.0'})
        rawData = urllib.request.urlopen(url=url1, context=gcontext).read().decode('utf-8')
        soup = bs.BeautifulSoup(rawData, 'html5lib')
        to_send = []
        index = 1
        for card_holder in soup.findAll('div', {"class": "small-12 medium-6 large-12 column"}):
            formatted_row = format_message_row(getRow(card_holder)
                , index)
            to_send.append(formatted_row)
            index = index + 1
        if len(to_send) == 0:
            return
        else:
            paginate_and_send_to_subscriber(bot,to_send,chat_id)
    except:
        return


# EXTRACT THE REQUIRED INFORMATION FROM SCRAPED TAGS
def getRow(card_holder):
    title = ''
    url = ''
    title_holder = card_holder.find('a', {"class": "ht-eb-card__title"})
    if title_holder is not None:
        title = title_holder.text
        url = title_holder['href']
    start_card = card_holder.find('div', {"class": "date date--start idea-ht-calendar-light"})
    start_date = ''
    if start_card is not None:
        for components in start_card:
            start_date = start_date + components.text + ' '
    end_card = card_holder.find('div', {"class": "date date--end idea-ht-calendar-light"})
    end_date = ''
    if end_card is not None:
        for components in end_card:
            end_date = end_date + components.text + ' '
    tags_holder = card_holder.find('div', {"class": "ht-card-tags"})
    tags = ''
    if tags_holder is not None:
        for tag in tags_holder:
            tags = tags + tag.text + ' '
    description = ''
    description_holder = card_holder.find('div', {"class": "ht-eb-card__description"})
    if not description_holder is None:
        description = description_holder.text
    location = ''
    location_holder = card_holder.find('span', {"class": "ht-eb-card__location__place"})
    if not location_holder is None:
        location = location_holder.text
    prize_title = ''
    prize_name = ''
    prize_holder = card_holder.find('div', {"class": "ht-eb-card__prize__container"})
    if prize_holder is not None:
        prize_title_holder = prize_holder.find('div', {"class", "ht-eb-card__prize__title"})
        if prize_title_holder is not None:
            prize_title = prize_title_holder.text
        prize_name_holder = prize_holder.find('div', {"class", "ht-eb-card__prize__name"})
        if prize_name_holder is not None:
            prize_name = prize_name_holder.text
    return [title, description, url, location, start_date,end_date,tags, prize_title, prize_name]

# FORMAT TH EXTRACTED TEXT TO SEND TO USER
def format_message_row(row_list,index):
    row=''
    for item in row_list:
        if not item=='':
            row=row+item+"\n"
    return {'text':str(index)+'. '+row+'\n','length':len(str(index)+'. '+row+'\n')}


# FUNCTION TO HANDLE PAGINATION AND SENDING TEXT TO USER
def paginate_and_send(bot,query,to_send):
    first=True
    tot_len=0
    message=''
    for row in to_send:
        if tot_len>=2500:
            if first:
                bot.edit_message_text(text=message,chat_id=query.message.chat_id,message_id=query.message.message_id,disable_web_page_preview=True)
                first=False
            else:
                bot.send_message(text=message,chat_id=query.message.chat_id,disable_web_page_preview=True)
            tot_len=0
            message=''
        message=message+row['text']
        tot_len=tot_len+row['length']
    if message !='':
        if first:
            bot.edit_message_text(text=message, chat_id=query.message.chat_id, message_id=query.message.message_id,disable_web_page_preview=True)
        else:
            bot.send_message(text=message, chat_id=query.message.chat_id,disable_web_page_preview=True)


# SAME AS ABOVE BUT FOR SUBSCRIBERS
def paginate_and_send_to_subscriber(bot,to_send,chat_id):
    try:
        tot_len = 0
        message = ''
        for row in to_send:
            if tot_len >= 2500:
                bot.send_message(text=message, chat_id=chat_id, disable_web_page_preview=True)
                tot_len = 0
                message = ''
            message = message + row['text']
            tot_len = tot_len + row['length']
        if message != '':
            bot.send_message(text=message, chat_id=chat_id, disable_web_page_preview=True)
    except Unauthorized:
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute("DELETE FROM subscribers WHERE id = (?)", (chat_id,))
        conn.commit()
        c.close()
        conn.close()


#................................................................................................




# START OF CONVERSATION HANDLER TO UNSUBSCRIBE
@timeouts.wrapper
def check_unsubscriber(bot,update,user_data,args):
    if (update.message.chat_id < 0):
        print(bot.get_chat_administrators(update.message.chat_id))
        if bot.get_chat_member(user_id=update.message.from_user.id,chat_id=update.message.chat_id) in bot.get_chat_administrators(update.message.chat_id):
            conn = sqlite3.connect(mount_point+'hk_bot.db')
            c = conn.cursor()
            c.execute('SELECT id FROM subscribers WHERE id=(?)', (str(update.message.chat_id),))
            if c.fetchone():
                keyboard = [[InlineKeyboardButton("Yes", callback_data='y5'),
                             InlineKeyboardButton("No", callback_data='n5')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('Are you sure you want to unsubscribe',reply_markup=reply_markup)
                return UNSUB_1
            else:
                update.message.reply_text('You are not subscribed. Please use /subscribe command to subscribe')
                return ConversationHandler.END
        else:
            update.message.reply_text('I am sorry. You dont have permission to perform this operation')
            return ConversationHandler.END
    else:
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute('SELECT id FROM subscribers WHERE id=(?)', (str(update.message.chat_id),))
        if c.fetchone():
            keyboard = [[InlineKeyboardButton("Yes", callback_data='y5'),
                         InlineKeyboardButton("No", callback_data='n5')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('Are you sure you want to unsubscribe', reply_markup=reply_markup)
            return UNSUB_1
        else:
            update.message.reply_text('You are not subscribed. Please use /subscribe command to subscribe')
            return ConversationHandler.END


def unsubscribe(bot,update,user_data):
    query=update.callback_query
    data=query.data
    if data=='y5':
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute('DELETE FROM subscribers WHERE id=(?)', (str(query.message.chat_id),))
        conn.commit()
        c.close()
        conn.close()
        bot.edit_message_text("Unsubscribed. Use command /subscribe to subscribe again",chat_id=query.message.chat_id,message_id=query.message.message_id)
    elif data == 'n5':
        bot.edit_message_text("Cancelled", chat_id=query.message.chat_id,
                              message_id=query.message.message_id)
    return ConversationHandler.END
# END OF CONVERSATION HANDLER TO UNSUBSCRIBE

# START OF CONVERSATION HANDLER TO SUBSCRIBE
@timeouts.wrapper
def check_subscriber(bot,update,user_data,args):
    if(update.message.chat_id<0):
        if bot.get_chat_member(user_id=update.message.from_user.id,chat_id=update.message.chat_id) in bot.get_chat_administrators(update.message.chat_id):
            update.message.reply_text("As this is a group I will require your location to set as the groups location")
            conn = sqlite3.connect(mount_point+'hk_bot.db')
            c = conn.cursor()
            c.execute('SELECT country,city FROM location WHERE id=(?)', (str(update.message.from_user.id),))
            data = c.fetchone()
            if not data:
                keyboard = [[InlineKeyboardButton("set location", url=BOT_URL+"?start=set_location")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('You have not set your location. Kindly set up your location and retry',
                                          reply_markup=reply_markup)
                user_data.clear()
                return ConversationHandler.END
            else:
                user_data['country'] = data[0]
                user_data['city'] = data[1]
                user_data['subscriber'] = update.message.chat_id
                keyboard = [[InlineKeyboardButton("Country", callback_data='country4'),
                             InlineKeyboardButton("City", callback_data='city4')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('Get a list of hackathons every week from your', reply_markup=reply_markup)
                return SUBS_2
        else:
            update.message.reply_text('I am sorry. You dont have permission to perform this operation')
            return ConversationHandler.END
    else:
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute('SELECT country,city FROM location WHERE id=(?)', (str(update.message.from_user.id),))
        data = c.fetchone()
        if not data:
            update.message.reply_text('You have not set your location. Kindly set up your location using /set_location and retry')
            user_data.clear()
            return ConversationHandler.END
        else:
            user_data['country'] = data[0]
            user_data['city'] = data[1]
            user_data['subscriber'] = update.message.chat_id
            keyboard = [[InlineKeyboardButton("Country", callback_data='country4'),
                         InlineKeyboardButton("City", callback_data='city4')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('Get a list of hackathons every week from your', reply_markup=reply_markup)
            return SUBS_2

def subscribe(bot,update,user_data):
    country=user_data['country']
    city=user_data['city']
    subscriber=user_data['subscriber']
    query=update.callback_query
    if query.data=='country4':
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO subscribers (id,country,city,coun1,cit1) VALUES (?,?,?,1,0)",
                  (str(subscriber), country, city))
        if c.rowcount == 0:
            bot.edit_message_text("Already subscribed. Kindly unsubscribe using /unsubscribe and try again",chat_id=query.message.chat_id,message_id=query.message.message_id)
        else:
            bot.edit_message_text("Subscribed :) . I will send upcoming hackathons every week",
                                  chat_id=query.message.chat_id, message_id=query.message.message_id)
        conn.commit()
        c.close()
        conn.close()
    elif query.data=='city4':
        conn = sqlite3.connect(mount_point+'hk_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO subscribers (id,country,city,coun1,cit1) VALUES (?,?,?,0,1)",
                  (str(subscriber), country, city))
        if c.rowcount == 0:
            bot.edit_message_text("Already subscribed. Kindly unsubscribe using /unsubscribe and try again",chat_id=query.message.chat_id,message_id=query.message.message_id)
        else:
            bot.edit_message_text("Subscribed :) . I will send upcoming hackathons every week",
                                  chat_id=query.message.chat_id, message_id=query.message.message_id)
        conn.commit()
        c.close()
        conn.close()
    return ConversationHandler.END
# END OF CONVERSATION HANDLER TO SUBSCRIBE




# START OF CONVERSATION HANDLER TO SET LOCATION
@timeouts.wrapper
def set_location(bot,update,user_data,args):
    location_key = KeyboardButton(text="send location", request_location=True)
    manual_key = KeyboardButton(text="set manually")
    custom_keyboard = [[location_key, manual_key]]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard)
    update.message.reply_text('Please choose option to set your location',
                              reply_markup=reply_markup)
    return SET_LOC

def recieve_set_loc(bot,update,user_data):
    location=update.message.location
    if location is not None:
        try:
            my_location = gmaps.reverse_geocode((location['latitude'], location['longitude']))
            address = my_location[0]['address_components']
            city = None
            country = None
            for components in address:
                if components['types'] == ['locality', 'political']:
                    city = str(components['long_name']).lower()
                if components['types'] == ['country', 'political']:
                    country = str(components['long_name']).lower()
                    break
            if country is not None:
                country=country.replace(' ','-')
            if city is not None:
                city=city.replace(' ','-')
            conn = sqlite3.connect(mount_point+'hk_bot.db')
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO location (id,country,city) VALUES (?,?,?)",
                      (str(update.message.from_user.id), country, city))
            if c.rowcount == 0:
                c.execute("UPDATE location SET country=(?),city=(?) WHERE id = (?) ",
                          (country, city, str(update.message.from_user.id)))
            c.execute("UPDATE subscribers SET country=(?),city=(?) WHERE id = (?) ",
                      (country, city, str(update.message.from_user.id)))
            conn.commit()
            c.close()
            conn.close()
            reply_markup = ReplyKeyboardRemove()
            update.message.reply_text('Location set\nCountry=' + country + "\nCity=" + city, reply_markup=reply_markup)
            return ConversationHandler.END
        except:
            update.message.reply_text('Sorry your location is not valid',reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
    else:
        if update.message.text=="set manually":
            update.message.reply_text('Send the name of your country', reply_markup=ForceReply(True))
            return SET_COUNTRY
        return ConversationHandler.END

def set_country(bot,update,user_data):
    country = update.message.text.lower().replace(' ','-')
    user_data['country'] = country
    update.message.reply_text('Send the name of your city', reply_markup=ForceReply(True))
    return SET_CITY

def set_city(bot,update,user_data):
    city = update.message.text.lower().replace(' ','-')
    user_data['city'] = city
    country = user_data['country']
    conn = sqlite3.connect(mount_point+'hk_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO location (id,country,city) VALUES (?,?,?)",
              (str(update.message.from_user.id), country, city))
    if c.rowcount == 0:
        c.execute("UPDATE location SET country=(?),city=(?) WHERE id = (?) ",
                  (country, city, str(update.message.from_user.id)))
    c.execute("UPDATE subscribers SET country=(?),city=(?) WHERE id = (?) ",
              (country, city, str(update.message.from_user.id)))
    conn.commit()
    c.close()
    conn.close()
    update.message.reply_text('Location set\nCountry=' + country + "\nCity=" + city)
    return ConversationHandler.END
# END OF CONVERSATION HANDLER TO SET LOCATION


# START OF CONVERSATION HANDLER FOR GETTING UPCOMING HACKATHONS
@timeouts.wrapper
def upcoming_menu1(bot,update,user_data,args):
    conn=sqlite3.connect(mount_point+'hk_bot.db')
    c=conn.cursor()
    c.execute('SELECT country,city FROM location WHERE id=(?)',(str(update.message.from_user.id),))
    data=c.fetchone()
    if not data and update.message.chat_id>0:
        location_key = KeyboardButton(text="send location", request_location=True)
        manual_key = KeyboardButton(text="set manually")
        custom_keyboard = [[location_key,manual_key]]
        reply_markup = ReplyKeyboardMarkup(custom_keyboard)
        update.message.reply_text('You have not set your location yet. Please send your location to continue',reply_markup=reply_markup)
        return REC_LOC
    elif not data and update.message.chat_id<0:
        keyboard = [[InlineKeyboardButton("open bot",url=BOT_URL+"?start=set_location")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('You have not set your location. Kindly set up your location at', reply_markup=reply_markup)
        return ConversationHandler.END
    else:
        user_data['country']=data[0]
        user_data['city']=data[1]
        keyboard = [[InlineKeyboardButton("Country", callback_data='country3'),
                     InlineKeyboardButton("City", callback_data='city3')]]
        reply_markup=InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Get a list of first 10 upcoming hackathons in your', reply_markup=reply_markup)
        return UPCM_2

def upcoming_menu2(bot,update,user_data):
    query=update.callback_query
    val=query.data
    if val == 'country3':
        url = 'https://www.hackathon.com/country/'+user_data['country']
        bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        fetcher(url,bot,query)
    elif val=='city3':
        url = 'https://www.hackathon.com/city/'+user_data['country']+'/'+user_data['city']
        bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        fetcher(url, bot, query)
    user_data.clear()
    return ConversationHandler.END


def recieve_location(bot,update,user_data):
    location=update.message.location
    if location is not None:
        try:
            my_location = gmaps.reverse_geocode((location['latitude'], location['longitude']))
            address = my_location[0]['address_components']
            city = None
            country = None
            for components in address:
                if components['types'] == ['locality', 'political']:
                    city = str(components['long_name']).lower()
                if components['types'] == ['country', 'political']:
                    country = str(components['long_name']).lower()
                    break
            if country is not None:
                country=country.replace(' ','-')
            if city is not None:
                city=city.replace(' ','-')
            conn = sqlite3.connect(mount_point+'hk_bot.db')
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO location (id,country,city) VALUES (?,?,?)",
                      (str(update.message.from_user.id), country, city))
            if c.rowcount == 0:
                c.execute("UPDATE location SET country=(?),city=(?) WHERE id = (?) ",
                          (country, city, str(update.message.from_user.id)))
            c.execute("UPDATE subscribers SET country=(?),city=(?) WHERE id = (?)",
                      (country, city, str(update.message.from_user.id)))
            conn.commit()
            c.close()
            conn.close()
            update.message.reply_text('Country = ' + country + '\nCity = ' + city, reply_markup=ReplyKeyboardRemove())
            user_data['country'] = country
            user_data['city'] = city
            keyboard = [[InlineKeyboardButton("Country", callback_data='country3'),
                         InlineKeyboardButton("City", callback_data='city3')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('Get a list of first 10 upcoming hackathons in your', reply_markup=reply_markup)
            return UPCM_2
        except:
            update.message.reply_text('Sorry your location is not valid',reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
    else:
        if update.message.text=="set manually":
            update.message.reply_text('Send the name of your country', reply_markup=ForceReply(True))
            return GET_COUNTRY
        return ConversationHandler.END



def get_country(bot,update,user_data):
    country=update.message.text.lower().replace(' ','-')
    user_data['country']=country
    update.message.reply_text('Send the name of your city', reply_markup=ForceReply(True))
    return GET_CITY


def get_city(bot,update,user_data):
    city=update.message.text.lower().replace(' ','-')
    user_data['city']=city
    country=user_data['country']
    conn = sqlite3.connect(mount_point+'hk_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO location (id,country,city) VALUES (?,?,?)",
              (str(update.message.from_user.id), country, city))
    if c.rowcount == 0:
        c.execute("UPDATE location SET country=(?),city=(?) WHERE id = (?) ",
                  (country, city, str(update.message.from_user.id)))
    c.execute("UPDATE subscribers SET country=(?),city=(?) WHERE id = (?)",(country, city, str(update.message.from_user.id)))
    conn.commit()
    c.close()
    conn.close()
    keyboard = [[InlineKeyboardButton("Country", callback_data='country3'),
                 InlineKeyboardButton("City", callback_data='city3')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Get a list of first 10 upcoming hackathons in your', reply_markup=reply_markup)
    return UPCM_2

# END OF CONVERSATION HANDLER FOR GETTING UPCOMING HACKATHONS




@timeouts.wrapper
def start(bot, update,user_data,args):
    if 'set_location' in args:
        return set_location(bot,update,user_data)
    else:
        update.message.reply_text("Welcome\nI can help you in finding upcoming hackathons near you\nUse command /upcoming to get upcoming hackathons\n/set_location to set your location.\n/subscribe to get list of upcoming hackathons"
                                  " every week\nYou can use /cancel any time to cancel operation\nTo see all the commands use /help"
                                  "\n\nORIGINAL CREATOR @gotham13121997\n\nORIGINAL SOURCE CODE \nhttps://github.com/Gotham13121997/HACKATHON-BOT")
        return ConversationHandler.END

@timeouts.wrapper
def help(bot, update,user_data,args):
    update.message.reply_text('/upcoming -> Get a list of upcoming hackathons\n'
                              '/set_location -> Set your location\n'
                              '/subscribe -> Get upcoming hacakthons every week\n'
                              '/unsubscribe -> Unsubscribe from the above\n'
                              '/cancel -> Cancel operation')
@timeouts.wrapper
def cancel(bot, update, user_data,args):
    update.message.reply_text('Cancelled',reply_markup=ReplyKeyboardRemove())
    user_data.clear()
    return ConversationHandler.END


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))

# START OF ADMIN COMMANDS
# START OF ADMIN CONVERSATION HANDLER TO BROADCAST MESSAGE
@timeouts.wrapper
def broadcast(bot,update,user_data,args):
    if not str(update.message.chat_id) in adminlist:
        update.message.reply_text("sorry you are not an admin")
        return ConversationHandler.END
    update.message.reply_text("Send your message")
    return BDC

def broadcast_message(bot,update):
    message = update.message.text
    conn = sqlite3.connect(mount_point + 'hk_bot.db')
    c = conn.cursor()
    c.execute('select id from location union select id from subscribers')
    for row in c.fetchall():
        try:
            bot.send_message(text=message,chat_id=row[0])
        except:
            pass
        time.sleep(1)
    c.close()
    conn.close()
    return ConversationHandler.END
# END OF ADMIN CONVERSATION HANDLER TO BROADCAST MESSAGE


# START OF ADMIN CONVERSATION HANDLER TO REPLACE THE DATABASE
@timeouts.wrapper
def getDb(bot, update,user_data,args):
    if not str(update.message.chat_id) in adminlist:
        update.message.reply_text("sorry you are not an admin")
        return ConversationHandler.END
    update.message.reply_text("send your sqlite database")
    return DB


def db(bot, update):
    file_id = update.message.document.file_id
    newFile = bot.get_file(file_id)
    newFile.download(mount_point+'hk_bot.db')
    update.message.reply_text("saved")
    return ConversationHandler.END
# END OF ADMIN CONVERSATION HANDLER TO REPLACE THE DATABASE

@timeouts.wrapper
def givememydb(bot, update,user_data,args):
    if not str(update.message.chat_id) in adminlist:
        update.message.reply_text("sorry you are not an admin")
        return
    bot.send_document(chat_id=update.message.chat_id, document=open(mount_point+'hk_bot.db', 'rb'))



# Write your handlers here
def setup(webhook_url=None):
    """If webhook_url is not passed, run with long-polling."""
    logging.basicConfig(level=logging.WARNING)
    if webhook_url:
        bot = Bot(TOKEN)
        update_queue = Queue()
        dp = Dispatcher(bot, update_queue)
    else:
        updater = Updater(TOKEN)
        bot = updater.bot
        dp = updater.dispatcher
        conv_handler1 = ConversationHandler(
            entry_points=[CommandHandler('upcoming',upcoming_menu1,pass_user_data=True,pass_args=True)],
            allow_reentry=True,
            states={
                REC_LOC: [MessageHandler(Filters.location|Filters.text,recieve_location,pass_user_data=True)],
                UPCM_2: [CallbackQueryHandler(upcoming_menu2,pattern=r'\w*3\b',pass_user_data=True)],
                GET_COUNTRY:[MessageHandler(Filters.text,get_country,pass_user_data=True)],
                GET_CITY:[MessageHandler(Filters.text,get_city,pass_user_data=True)]
            },
            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )

        conv_handler2=ConversationHandler(
            entry_points=[CommandHandler('set_location', set_location, pass_user_data=True,pass_args=True),
                          CommandHandler("start", start, pass_args=True, pass_user_data=True)],
            allow_reentry=True,
            states={
                SET_LOC: [MessageHandler(Filters.location | Filters.text, recieve_set_loc, pass_user_data=True)],
                SET_COUNTRY: [MessageHandler(Filters.text, set_country, pass_user_data=True)],
                SET_CITY: [MessageHandler(Filters.text, set_city, pass_user_data=True)]
            },
            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )
        conv_handler3 = ConversationHandler(
            entry_points=[CommandHandler('subscribe',check_subscriber, pass_user_data=True, pass_args=True)],
            allow_reentry=True,
            states={
                SUBS_2: [CallbackQueryHandler(subscribe, pattern=r'\w*4\b', pass_user_data=True)],
            },
            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )
        conv_handler4 = ConversationHandler(
            entry_points=[CommandHandler('unsubscribe', check_unsubscriber, pass_user_data=True,pass_args=True)],
            allow_reentry=True,
            states={
                UNSUB_1: [CallbackQueryHandler(unsubscribe, pattern=r'\w*5\b', pass_user_data=True)],
            },
            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )
        # ADMIN CONVERSATION HANDLER TO BROADCAST MESSAGES
        conv_handler5 = ConversationHandler(
            entry_points=[CommandHandler('broadcast', broadcast,pass_args=True,pass_user_data=True)],
            allow_reentry=True,
            states={
                BDC: [MessageHandler(Filters.text, broadcast_message)]
            },

            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )
        # CONVERSATION HANDLER FOR REPLACING SQLITE DATABASE
        conv_handler6 = ConversationHandler(
            entry_points=[CommandHandler('senddb', getDb,pass_user_data=True,pass_args=True)],
            allow_reentry=True,
            states={
                DB: [MessageHandler(Filters.document, db)]
            },

            fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_args=True)]
        )
        dp.add_handler(conv_handler1)
        dp.add_handler(conv_handler2)
        dp.add_handler(conv_handler3)
        dp.add_handler(conv_handler4)
        dp.add_handler(conv_handler5)
        dp.add_handler(conv_handler6)
        dp.add_handler(CommandHandler('givememydb', givememydb,pass_args=True,pass_user_data=True))
        dp.add_handler(CommandHandler('help',help,pass_user_data=True,pass_args=True))
        # log all errors
        dp.add_error_handler(error)
    # Add your handlers here
    if webhook_url:
        bot.set_webhook(webhook_url=webhook_url)
        thread = Thread(target=dp.start, name='dispatcher')
        thread.start()
        return update_queue, bot
    else:
        bot.set_webhook()  # Delete webhook
        updater.start_polling()
        updater.idle()


if __name__ == '__main__':
    setup()