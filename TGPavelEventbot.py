import os
import logging
import time
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, CallbackContext


load_dotenv()
EVENT_TOKEN = os.getenv('EventBot_TOKEN')

# logger at info level
logging.basicConfig(filename='event.log',
                    filemode='a',
                    format='%(asctime)s | %(levelname)s: %(message)s',
                    level='INFO',
                    encoding='utf-8')
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())


async def start(update: Update, context: CallbackContext) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot to organize events."
                                                                          "Print /event EVENT NAME to create event\n")


async def help_command(update: Update, context: CallbackContext) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Print "/event EVENT NAME to create event\n'
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
async def create_event(update: Update, context: CallbackContext) -> None:
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text=name + text, reply_markup=reply_markup)


# close or open event
async def change_state(query, text_message) -> None:
    if text_message[:16] != "❌ EVENT CLOSED ❌":
        text_message = '❌ EVENT CLOSED ❌\n' + text_message
        keyboard = closed_keyboard()
    else:
        text_message = text_message[17:]
        keyboard = base_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text_message, reply_markup=reply_markup, parse_mode='Markdown')


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
async def go_event(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❎ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('❔ ' + message))
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not going😐:", message, '✅')
        await count_people(query, text_message, reply_markup)


# adds user to list of people, who are not going
async def not_go(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('❔ ' + message))
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not sure🤔:", message, '❎')
        await count_people(query, text_message, reply_markup)


# adds user to list of people, who are not sure
async def not_sure(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    if '✅ ' + message in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❎ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❎ ' + message))
    if '❔ ' + message in temp[temp.index("Not sure🤔:"):-5]:
        pass
    else:
        text_message = add_to_message(temp, temp[-5], message, '❔')
        await count_people(query, text_message, reply_markup)


# adds people to list of people, who will go with main participant
async def add(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) + 1
            temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            break
        else:
            text_message = add_to_message(temp, "Not going😐:", message, f'➕1, from:')
    await count_people(query, text_message, reply_markup)


# deletes people from list of people, who will go with main participant
async def sub(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) - 1
            if number <= 0:
                temp.pop(temp.index(people))
            else:
                temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            await count_people(query, text_message, reply_markup)
        else:
            pass


# deletes all people from list of people, who will go with main participant
async def sub_all(query, text_message) -> None:
    message, reply_markup, temp = press(query, text_message)
    for people in temp[temp.index("Going🙂:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            temp.pop(temp.index(people))
            text_message = "\n".join(m for m in temp)
            await count_people(query, text_message, reply_markup)
        else:
            pass


# counts all categories of people, this function is called after each add or sub
async def count_people(query, text_message, reply_markup) -> None:
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
    await query.edit_message_text(text_message, reply_markup=reply_markup, parse_mode='Markdown')


# handle buttons pressed on keyboard
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    text_message = query.message.text_markdown_v2
    await query.answer()
    if query.data == 'Change_state':
        await change_state(query, text_message)
    elif query.data == 'Go':
        await go_event(query, text_message)
    elif query.data == 'Not_go':
        await not_go(query, text_message)
    elif query.data == 'Not_sure':
        await not_sure(query, text_message)
    elif query.data == 'Add':
        await add(query, text_message)
    elif query.data == 'Sub':
        await sub(query, text_message)
    elif query.data == 'Sub_all':
        await sub_all(query, text_message)


def eventbot() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(EVENT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('event', create_event))
    application.add_handler(CallbackQueryHandler(button))
    # Run the bot until the user presses Ctrl-C
    application.run_polling()


eventbot()
