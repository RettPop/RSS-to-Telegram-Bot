#!/usr/bin/env python3

import feedparser
import logging
import sqlite3
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from pathlib import Path
import sys

Path("config").mkdir(parents=True, exist_ok=True)

# Docker env
if os.environ.get('TOKEN'):
    Token = os.environ['TOKEN']
    chatid = os.environ['CHATID']
    delay = int(os.environ['DELAY'])
else:
    Token = sys.argv[1]
    chatid = sys.argv[2]
    delay = 30

if Token == "X":
    print("Token not set!")

rss_dict = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# SQLITE


def sqlite_connect():
    global conn
    conn = sqlite3.connect('config/rss.db', check_same_thread=False)

def sqlite_load_all():
    sqlite_connect()
    c = conn.cursor()
    c.execute('SELECT * FROM rss')
    rows = c.fetchall()
    conn.close()
    return rows


def sqlite_write(name, link, last):
    sqlite_connect()
    c = conn.cursor()
    q = [(name), (link), (last)]
    c.execute('''INSERT INTO rss('name','link','last') VALUES(?,?,?)''', q)
    conn.commit()
    conn.close()

COL_TITLE = 0
COL_LINK = 1
COL_LAST = 2

# RSS________________________________________
def rss_load():
    # if the dict is not empty, empty it.
    if bool(rss_dict):
        rss_dict.clear()

    for row in sqlite_load_all():
        rss_dict[row[COL_TITLE]] = (row[COL_LINK], row[COL_LAST])


def cmd_rss_list(update, context):
    if bool(rss_dict) is False:

        update.effective_message.reply_text("The database is empty")
    else:
        for title, rss_params in rss_dict.items():
            update.effective_message.reply_text(
                "Title: " + title +
                "\nrss url: " + rss_params[0] +
                "\nlast checked article: " + rss_params[1])


def cmd_rss_add(update, context):
    # try if there are 2 arguments passed
    try:
        context.args[1]
    except IndexError:
        update.effective_message.reply_text(
            "ERROR: The format needs to be: /add title http://www.URL.com")
        raise
    # try if the url is a valid RSS feed
    try:
        rss_d = feedparser.parse(context.args[1])
        rss_d.entries[0]['title']
    except IndexError as e:
        update.effective_message.reply_text(
            "ERROR: The link does not seem to be a RSS feed or is not supported: {0}".format(e))
        raise
    sqlite_write(context.args[0], context.args[1],
                 str(rss_d.entries[0]['link']))
    rss_load()
    update.effective_message.reply_text(
        "added \nTITLE: %s\nRSS: %s" % (context.args[0], context.args[1]))


def cmd_rss_remove(update, context):
    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    q = (context.args[0],)
    try:
        c.execute("DELETE FROM rss WHERE name = ?", q)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
    rss_load()
    update.effective_message.reply_text("Removed: " + context.args[0])


def cmd_help(update, context):
    print("Received message from chat {0}".format(update))
    update.effective_message.reply_markdown_v2(
        "RSS to Telegram bot" +
        "\n\nAfter successfully adding a RSS link, the bot starts fetching the feed every "
        + str(delay) + " seconds\. \(This can be set\)" +
        "\n\nTitles are used to easily manage RSS feeds and need to contain only one word" +
        "\n\ncommands:" +
        "\n/help Posts this help message" +
        "\n/add title http://www\.RSS\-URL\.com" +
        "\n/remove Title removes the RSS link" +
        "\n/list Lists all the titles and the RSS links from the DB" +
        "\n/test Inbuilt command that fetches a post from Reddits RSS\." +
        "\n\nThe current chatId is: " + str(update.message.chat.id) +
        "\n\nIf you like the project, star it on [DockerHub](https://hub.docker.com/r/bokker/rss.to.telegram)")

PARAM_LINK = 0
PARAM_LAST = 1
def rss_monitor(context):
    for feed_title, feed_params in rss_dict.items():
        feed_last_item = feed_params[PARAM_LAST]
        feed_link = feed_params[PARAM_LINK]
        rss_d = feedparser.parse(feed_params[PARAM_LINK])
        feed_entries = rss_d.entries
        cnt_new_items = 0
        for entry in feed_entries:
            # if we reached last record, it means we fetched all new records
            if (feed_last_item == entry['link']):
                if cnt_new_items > 0:
                    print("Feer {1} has {0} items, new: {2} ".format(len(feed_entries), feed_title, cnt_new_items))
                break
            #write only first item -- the latest one
            if cnt_new_items == 0:
                conn = sqlite3.connect('config/rss.db')
                q = [(feed_title), (feed_link), (str(entry['link']))]
                c = conn.cursor()
                c.execute(
                    '''INSERT INTO rss('name','link','last') VALUES(?,?,?)''', q)
                conn.commit()
                conn.close()
                rss_load()
            cnt_new_items += 1
            message = "{0}\nURL: {1}\nPublished: {2}\n<i>From: {3}</i>".format(entry['title'], entry['link'], entry['updated'], feed_title)
            context.bot.send_message(chatid, message)
            print("Got item in RSS {0} link {1}. Updated {2}".format(feed_title, entry['link'], entry['updated']))


def cmd_test(update, context):
    url = "https://www.reddit.com/r/funny/new/.rss"
    rss_d = feedparser.parse(url)
    rss_d.entries[0]['link']
    update.effective_message.reply_text(
        rss_d.entries[0]['title'] + "\n" +
        rss_d.entries[0]['link'])


def init_sqlite():
    users_conn = sqlite3.connect('config/users.db')
    users_cursor = users_conn.cursor()
    users_cursor.execute('''CREATE TABLE users (name text, id text)''')

    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE rss (name text, link text, last text)''')
    c.execute('''CREATE TABLE channels (name text, id text)''')

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

def echo(update, context):
    if update.message:
        context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
        context.bot.send_message(chat_id=update.effective_chat.id, text=update.effective_chat.id)
    if update.channel_post:
        # context.bot.send_message(chat_id=update.effective_chat.id, text=update.channel_post.text)
        # context.bot.send_message(chat_id=update.effective_chat.id, text=update.channel_post.chat_id)
        context.bot.send_message(chat_id=172085054, text=update.channel_post.text)
        # context.bot.send_message(chat_id=update.effective_chat.id, text=update.channel_post.chat_id)


def main():
    updater = Updater(token=Token, use_context=True)
    job_queue = updater.job_queue
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("add", cmd_rss_add))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("test", cmd_test, ))
    dp.add_handler(CommandHandler("list", cmd_rss_list))
    dp.add_handler(CommandHandler("remove", cmd_rss_remove))
    
    start_handler = CommandHandler('start', start)
    dp.add_handler(start_handler)

    echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
    dp.add_handler(echo_handler)

    # try to create a database if missing
    try:
        init_sqlite()
    except sqlite3.OperationalError:
        pass
    rss_load()

    job_queue.run_repeating(rss_monitor, delay)

    updater.start_polling()
    updater.idle()
    conn.close()


if __name__ == '__main__':
    main()
