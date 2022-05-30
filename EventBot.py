import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, Updater, MessageHandler, Filters, CommandHandler,  CallbackQueryHandler
import logging
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('EventBot_TOKEN')

# logger at info level
logging.basicConfig(filename='event.log',
                    filemode='a',
                    format='%(asctime)s | %(levelname)s: %(message)s',
                    level='INFO',
                    encoding='utf-8')
logger = logging.getLogger()


updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher


def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot to organize events."
                                                                    "Print /event EVENT NAME to create event\n")


# test function, not actually used
def print_what_you_get(update: Update, context: CallbackContext):
    text = context.args
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def help_bot(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text='Print "/event EVENT NAME to create event\n'
                                                                    'Print /start to get start message\n')


# keyboard layout with opportunity to go and cancel go
def base_keyboard():
    keyboard = [[InlineKeyboardButton("Close event", callback_data='Change_state')],
                [InlineKeyboardButton("✅ Going ", callback_data='Go'),
                 InlineKeyboardButton("❎ Not going", callback_data='Not_go'),
                 InlineKeyboardButton("🤔 Not sure", callback_data='Not_sure')],
                [InlineKeyboardButton("Add ", callback_data='Add'),
                 InlineKeyboardButton("Sub", callback_data='Sub'),
                 InlineKeyboardButton("Sub all", callback_data='Sub_all')]]
    return keyboard


# keyboard layout with opportunity to cancel go
def closed_keyboard():
    keyboard = [[InlineKeyboardButton("Open event", callback_data='Change_state')],
                [InlineKeyboardButton("❎ Not going", callback_data='Not_go')],
                [InlineKeyboardButton("Sub", callback_data='Sub'),
                 InlineKeyboardButton("Sub all", callback_data='Sub_all')]]
    return keyboard


# function for creating event message
def create_event(update: Update, context: CallbackContext):
    if not context.args:
        name = '👉   No name event   👈\n'
    else:
        name = '👉   ' + ' '.join(item for item in context.args) + '   👈\n'
    text = "Going🙂:\n" \
           "Not going😐:\n" \
           "Not sure🤔:\n" \
           "Total going:\n" \
           "✅:\n" \
           "➕:\n" \
           "❎:\n" \
           "❔:" \

    keyboard = base_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=name + text, reply_markup=reply_markup)


# close or open event
def change_state(query, text_message):
    if text_message[:16] != "❌ EVENT CLOSED ❌":
        text_message = '❌ EVENT CLOSED ❌\n' + text_message
        keyboard = closed_keyboard()
    else:
        text_message = text_message[17:]
        keyboard = base_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text_message, reply_markup=reply_markup, parse_mode='Markdown')


# get user who pressed button, check for keyboard and splits messages in categories
def press(query, text_message):
    message = query.from_user.mention_markdown_v2()
    if text_message[:16] != "❌ EVENT CLOSED ❌":
        keyboard = base_keyboard()
    else:
        keyboard = closed_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    temp = text_message.split("\n")
    return message, reply_markup, temp


# places name in specified position
def add_to_message(temp, index, message, mind):
    if mind != "✅":
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    else:
        plus_list = []
        for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
            if "➕" in people:
                plus_list.append(temp.pop(temp.index(people)))
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        if plus_list:
            end_text = "\n" + "\n".join(m for m in plus_list) + "\n" + "\n".join(m for m in temp[temp.index(index):])
        else:
            end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    return text_message


# adds user to list of people, who are going
def go_event(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❎ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('❔ ' + message))
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not going😐:", message, '✅')
        count_people(query, text_message, reply_markup)


# adds user to list of people, who are not going
def not_go(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('❔ ' + message))
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not sure🤔:", message, '❎')
        count_people(query, text_message, reply_markup)


# adds user to list of people, who are not sure
def not_sure(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❎ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        pass
    else:
        text_message = add_to_message(temp, temp[-5], message, '❔')
        count_people(query, text_message, reply_markup)


# adds people to list of people, who will go with main participant
def add(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) + 1
            temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            break
        else:
            text_message = add_to_message(temp, "Not going😐:", message, f'➕1, from:')
    count_people(query, text_message, reply_markup)


# deletes people from list of people, who will go with main participant
def sub(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) - 1
            if number <= 0:
                temp.pop(temp.index(people))
            else:
                temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            count_people(query, text_message, reply_markup)
        else:
            pass


# deletes all people from list of people, who will go with main participant
def sub_all(query, text_message):
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            temp.pop(temp.index(people))
            text_message = "\n".join(m for m in temp)
            count_people(query, text_message, reply_markup)
        else:
            pass


# counts all categories of people, this function is called after each add or sub
def count_people(query, text_message, reply_markup):
    temp = text_message.split("\n")
    temp_count = temp[:-5]
    going = 0
    going_plus = 0
    not_going = 0
    in_doubt = 0
    for pos in temp_count:
        if "✅" in pos:
            going += 1
        elif "❎" in pos:
            not_going += 1
        elif "❔" in pos:
            in_doubt += 1
        elif "➕" in pos:
            going_plus += int(pos[1:pos.index(", from:")])
    temp[-5] = f"Total going: {going + going_plus}"
    temp[-4] = f"✅: {going}"
    temp[-3] = f"➕: {going_plus}"
    temp[-2] = f"❎: {not_going}"
    temp[-1] = f"❔: {in_doubt}"
    text_message = "\n".join(m for m in temp)
    query.edit_message_text(text_message, reply_markup=reply_markup, parse_mode='Markdown')


# handle buttons pressed on keyboard
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    text_message = query.message.text_markdown_v2
    query.answer()
    if query.data == 'Change_state':
        change_state(query, text_message)
    elif query.data == 'Go':
        go_event(query, text_message)
    elif query.data == 'Not_go':
        not_go(query, text_message)
    elif query.data == 'Not_sure':
        not_sure(query, text_message)
    elif query.data == 'Add':
        add(query, text_message)
    elif query.data == 'Sub':
        sub(query, text_message)
    elif query.data == 'Sub_all':
        sub_all(query, text_message)


# add commands to bot
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('list', print_what_you_get))
dispatcher.add_handler(CommandHandler('help', help_bot))
dispatcher.add_handler(CommandHandler('event', create_event))
dispatcher.add_handler(CallbackQueryHandler(button))

# start the until exit (CTRL + C)
updater.start_polling(timeout=10)
print("EventBot started, press CTRL+C for stop and wait a bit.")
updater.idle()
print("EventBot stopped")

# python EventBot.py
