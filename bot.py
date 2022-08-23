"""
Moderation bot for comments at knife.media
"""
import os
import re
import threading
import html
import sys
import requests
import telebot
import mysql.connector

from dotenv import load_dotenv
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from lists.moderation import badwords

load_dotenv()

try:
    db = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASS"),
        database=os.getenv("MYSQL_NAME"),
        auth_plugin="mysql_native_password"
    )

except mysql.connector.Error as error:
    print("Mysql connection error: " + error.msg)
    sys.exit()


bot = telebot.TeleBot(os.getenv("TELEGRAM_TOKEN"))


def get_link(post, id):
    """ Get direct comment link by post id """

    link = os.getenv("SHORT_LINK") + post
    resp = requests.get(link)

    return resp.url + "#comment-" + id


def send_message(chat, text, markup):
    """ Send message to Telegram """

    bot.send_message(chat, text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=1)


def edit_message(chat, text, id):
    """ Edit message in Telegram """

    bot.edit_message_text(text, chat, id, parse_mode="HTML", disable_web_page_preview=1)


def show_warning(content, id, post):
    """ Show warning to Telegram bot """

    buttons = []
    buttons.append(InlineKeyboardButton("Удалить", None, "remove-" + id))
    buttons.append(InlineKeyboardButton("Заблокировать", None, "block-" + id))
    buttons.append(InlineKeyboardButton("Оставить", None, "leave-" + id))

    markup = InlineKeyboardMarkup()
    markup.row(*buttons)

    text = html.escape(content) + "\n\n" + get_link(post, id)

    # Send comment with moderation buttons
    send_message(os.getenv("TELEGRAM_CHAT"), text, markup)


def search_links(content):
    """ Search links in comment content """

    return re.search(r"(?:https?://)|(?:@)|(?:[0-9-]{6,})", content)


def search_hate(content):
    """ Search hate speech in comment """

    return any(word in content for word in badwords)


def check_database():
    """ Find unreveiwed comments """

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, post_id, content FROM comments "
            "LEFT JOIN watchcat ON comments.id = watchcat.comment_id "
            "WHERE comments.status = 'visible' "
            "AND watchcat.reviewed IS NULL LIMIT 50"
        )

        result = cursor.fetchall()

        for row in result:
            id, post, content = map(str, row.values())

            if search_hate(content) or search_links(content):
                show_warning(content, id, post)

            cursor.execute("INSERT IGNORE INTO watchcat (comment_id) VALUES (%s)", [id])

        db.commit()

    finally:
        cursor.close()

    scheduler = threading.Timer(120.0, check_database)
    scheduler.start()


scheduler = threading.Timer(2.0, check_database)
scheduler.start()


def remove_comment(message, id):
    """ Remove comment by id """

    cursor = db.cursor(dictionary=True)

    try:
        # Remove single comment
        cursor.execute("UPDATE comments SET status = 'removed' WHERE id = %s", [id])

        db.commit()

        text = "<b>Удалено</b>: " + html.escape(message.text)
        edit_message(message.chat.id, text, message.message_id)
    finally:
        cursor.close()


def block_user(message, id):
    """ Block user and remove all his comments """

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT user_id AS user FROM comments WHERE id = %s", [id])
        result = cursor.fetchone()

        if result is None:
            return

        user = result["user"]

        # Block user
        cursor.execute("UPDATE users SET status = 'blocked' WHERE id = %s", [user])

        # Remove all comments
        cursor.execute("UPDATE comments SET status = 'removed' WHERE user_id = %s", [user])

        db.commit()

        text = "<b>Заблокировано</b>: " + html.escape(message.text)
        edit_message(message.chat.id, text, message.message_id)
    finally:
        cursor.close()


def hide_buttons(message):
    """ Hide buttons for Telegram message """

    text = "<b>Одобрено</b>: " + html.escape(message.text)
    edit_message(message.chat.id, text, message.message_id)


@bot.callback_query_handler(func=lambda call: True)
def bot_handle_calls(call):
    action, id = call.data.split("-")

    if action == "remove":
        remove_comment(call.message, id)

    if action == "block":
        block_user(call.message, id)

    if action == "leave":
        hide_buttons(call.message)


bot.infinity_polling()
