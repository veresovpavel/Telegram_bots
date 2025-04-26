import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os

# Telegram Access
token = os.getenv('token')
bot = telebot.TeleBot(token, threaded=False)


# Parser HTML
def parse_html(user):
    tg_id = user.id
    name = user.full_name
    html_text = f'<a href="tg://user?id={tg_id}">{name}</a>'
    return html_text


# Cloud Function Handler
def handler(event, context):
    body = json.loads(event['body'])
    update = telebot.types.Update.de_json(body)
    bot.process_new_updates([update])


# Start
@bot.message_handler(commands=['start'])
def start_helper(message) -> None:
    start_message = "I'm a bot to organize events. Print /event EVENT NAME to create event\n"
    bot.send_message(message.chat.id, start_message)


# Help
@bot.message_handler(commands=['help'])
def helper(message) -> None:
    help_message = 'Print "/event" EVENT NAME to create event\nPrint "/start" to get start message\n' \
                   'Print /description to get description (in Russian)'
    bot.send_message(message.chat.id, help_message)


# Description of bot functions
@bot.message_handler(commands=['description'])
def description(message) -> None:
    description_message = "Для создания опроса введите команду '/event', "\
                          "указав название этого опроса.\n"\
                          "Кнопка ✅ Going добавит вас в список тех, кто идет.\n"\
                          "Кнопка ❌ Not going добавит вас в список тех, кто не идет.\n"\
                          "Кнопка 💭 Not sure добавит вас в список тех, кто сомневается, что идет.\n"\
                          "При нажатии кнопки Add ваш + будет добавлен в список, то есть количество "\
                          "людей, которые придут с вами.\n"\
                          "При нажатии кнопки Sub будет убран 1 ваш +.\n"\
                          "При нажатии кнопки Sub all будут убраны все ваши +.\n"
    bot.send_message(message.chat.id, description_message)


# function for creating event message
@bot.message_handler(commands=['event'])
def create_event(message) -> None:
    if len(message.text.split()) == 1:
        name = '👉   No name event   👈\n'
    else:
        name = '👉   ' + ' '.join(item for item in message.text.split()[1:]) + '   👈\n'
    text = "Going😀🥅:\n" \
           "Going😀:\n" \
           "Not going😐:\n" \
           "Not sure🤔:\n" \
           "Total going:\n" \
           "✅:\n" \
           "➕:\n" \
           "❌:\n" \
           "💭:"
    bot.send_message(message.chat.id, name + text, reply_markup=base_keyboard(),  parse_mode="HTML")


# keyboard layout with opportunity to go and cancel go
def base_keyboard():
    keyboard = InlineKeyboardMarkup()
    key_change_state = InlineKeyboardButton(text="Close event", callback_data="change_state")
    key_go = InlineKeyboardButton(text="✅ Going ", callback_data="Go")
    key_not_go = InlineKeyboardButton(text="❌ Not going", callback_data="Not_go")
    key_not_sure = InlineKeyboardButton(text="💭 Not sure", callback_data='Not_sure')
    key_add = InlineKeyboardButton(text="➕ Add ", callback_data='Add')
    key_sub = InlineKeyboardButton(text="➖ Sub", callback_data='Sub')
    key_sub_all = InlineKeyboardButton(text="➖ Sub all", callback_data='Sub_all')
    key_go_keeper = InlineKeyboardButton(text="✅🥅 Going ", callback_data="Go_keeper")
    key_add_keeper = InlineKeyboardButton(text="➕🥅 Add ", callback_data='Add_keeper')
    key_sub_keeper = InlineKeyboardButton(text="➖🥅 Sub", callback_data='Sub_keeper')
    keyboard.row(key_change_state)
    keyboard.row(key_go, key_not_go, key_not_sure)
    keyboard.row(key_add, key_sub, key_sub_all)
    keyboard.row(key_go_keeper, key_add_keeper, key_sub_keeper)
    return keyboard


# keyboard layout with opportunity to cancel go
def closed_keyboard():
    keyboard = InlineKeyboardMarkup()
    key_change_state = InlineKeyboardButton(text="Open event", callback_data="change_state")
    key_not_go = InlineKeyboardButton(text="❌ Not going", callback_data="Not_go")
    key_sub = InlineKeyboardButton(text="➖ Sub", callback_data='Sub')
    key_sub_all = InlineKeyboardButton(text="➖ Sub all", callback_data='Sub_all')
    key_sub_keeper = InlineKeyboardButton(text="➖🥅 Sub", callback_data='Sub_keeper')
    keyboard.row(key_change_state)
    keyboard.row(key_not_go)
    keyboard.row(key_sub, key_sub_all)
    keyboard.row(key_sub_keeper)
    return keyboard


# Change keyboard to open or closed if user is admin of the chat
def change_state(call) -> None:
    text_message = call.message.html_text
    if (bot.get_chat_member(call.message.chat.id, call.from_user.id).status in ['administrator', 'creator']) \
            or (call.message.chat.type == "private"):
        if text_message[:16] != "❌ EVENT CLOSED ❌":
            text_message = '❌ EVENT CLOSED ❌\n' + text_message
            keyboard = closed_keyboard()
            bot.answer_callback_query(call.id, text="You closed event")
        else:
            text_message = text_message[17:]
            keyboard = base_keyboard()
            bot.answer_callback_query(call.id, text="You opened event")
        bot.edit_message_text(text_message, call.message.chat.id, call.message.id, reply_markup=keyboard, parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, text="You do not have permission to open or close event")


# counts all categories of people, this function is called after each add or sub
def count_people(call, text_message, keyboard) -> None:
    temp = text_message.split("\n")
    temp_count = temp[:-5]
    going = 0
    going_plus = 0
    not_going = 0
    in_doubt = 0
    for pos in temp_count:
        if "✅" in pos:
            going += 1
        elif ("❌" in pos) and (pos != "❌ EVENT CLOSED ❌"):
            not_going += 1
        elif "💭" in pos:
            in_doubt += 1
        elif "➕" in pos:
            if "➕🥅" in pos:
                going_plus += int(pos[2:pos.index(", from:")])
            else:
                going_plus += int(pos[1:pos.index(", from:")])
    temp[-5] = f"Total going: {going + going_plus}"
    temp[-4] = f"✅: {going}"
    temp[-3] = f"➕: {going_plus}"
    temp[-2] = f"❌: {not_going}"
    temp[-1] = f"💭: {in_doubt}"
    text_message = "\n".join(m for m in temp)
    bot.edit_message_text(text_message, call.message.chat.id, call.message.id, reply_markup=keyboard, parse_mode="HTML")


# get user who pressed button, check for keyboard and splits messages in categories
def press(call):
    text_message = call.message.html_text
    message = parse_html(call.from_user)
    if text_message[:16] != "❌ EVENT CLOSED ❌":
        keyboard = base_keyboard()
    else:
        keyboard = closed_keyboard()
    temp = text_message.split("\n")
    return message, keyboard, temp


# places name in specified position
def add_to_message(temp, index, message, mind) -> str:
    if mind != "✅":
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    else:
        plus_list = []
        if index == "Going😀:":
            for people in temp[temp.index("Going😀🥅:"):temp.index("Going😀:")]:
                if "➕🥅" in people:
                    plus_list.append(temp.pop(temp.index(people)))
        elif index == "Not going😐:":
            for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
                if ("➕" in people):
                    plus_list.append(temp.pop(temp.index(people)))
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        if plus_list:
            end_text = "\n" + "\n".join(m for m in plus_list) + "\n" + "\n".join(m for m in temp[temp.index(index):])
        else:
            end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    return text_message


# Adds user to list of people, who are going
def go_event(call) -> None:
    message, keyboard, temp = press(call)
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❌ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('💭 ' + message))
    if '✅ ' + message in temp[temp.index("Going😀🥅:"):temp.index("Going😀:")]:
        temp.pop(temp.index('✅ ' + message))
    if '✅ ' + message in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not going😐:", message, '✅')
        count_people(call, text_message, keyboard)


# Adds user to list of keeper people, who are going
def go_event_keeper(call) -> None:
    message, keyboard, temp = press(call)
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❌ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('💭 ' + message))
    if '✅ ' + message in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '✅ ' + message in temp[temp.index("Going😀🥅:"):temp.index("Going😀:")]:
        pass
    else:
        text_message = add_to_message(temp, "Going😀:", message, '✅')
        count_people(call, text_message, keyboard)


# adds user to list of people, who are not going
def not_go(call) -> None:
    message, keyboard, temp = press(call)
    if '✅ ' + message in temp[temp.index("Going😀🥅:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('💭 ' + message))
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not sure🤔:", message, '❌')
        count_people(call, text_message, keyboard)


# adds user to list of people, who are not sure
def not_sure(call) -> None:
    message, keyboard, temp = press(call)
    if '✅ ' + message in temp[temp.index("Going😀🥅:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❌ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        pass
    else:
        text_message = add_to_message(temp, temp[-5], message, '💭')
        count_people(call, text_message, keyboard)


# adds people to list of people, who will go with main participant
def add(call) -> None:
    message, keyboard, temp = press(call)
    text_message = call.message.html_text
    for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) + 1
            temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            break
        else:
            text_message = add_to_message(temp, "Not going😐:", message, f'➕1, from:')
    count_people(call, text_message, keyboard)


# adds people to list of people, who will go with main participant
def add_keeper(call) -> None:
    message, keyboard, temp = press(call)
    text_message = call.message.html_text
    for people in temp[temp.index("Going😀🥅:"):temp.index("Going😀:")]:
        if ("➕🥅" in people) and (message in people):
            number = int(people[2:people.index(", from:")]) + 1
            temp[temp.index(people)] = f"➕🥅{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            break
        else:
            text_message = add_to_message(temp, "Going😀:", message, f'➕🥅1, from:')
    count_people(call, text_message, keyboard)


# deletes people from list of people, who will go with main participant
def sub(call) -> None:
    message, keyboard, temp = press(call)
    for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) - 1
            if number <= 0:
                temp.pop(temp.index(people))
            else:
                temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            count_people(call, text_message, keyboard)
        else:
            pass


# deletes people from list of people, who will go with main participant
def sub_keeper(call) -> None:
    message, keyboard, temp = press(call)
    for people in temp[temp.index("Going😀🥅:"):temp.index("Going😀:")]:
        if ("➕🥅" in people) and (message in people):
            number = int(people[2:people.index(", from:")]) - 1
            if number <= 0:
                temp.pop(temp.index(people))
            else:
                temp[temp.index(people)] = f"➕🥅{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            count_people(call, text_message, keyboard)
        else:
            pass


# deletes all people from list of people, who will go with main participant
def sub_all(call) -> None:
    message, keyboard, temp = press(call)
    for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            temp.pop(temp.index(people))
            text_message = "\n".join(m for m in temp)
            count_people(call, text_message, keyboard)
        else:
            pass


# Gets callbacks from inline keyboard and answers them
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "change_state":
        change_state(call)
    elif call.data == 'Go':
        bot.answer_callback_query(call.id, text=f"You pressed ✅ Going")
        go_event(call)
    elif call.data == 'Not_go':
        bot.answer_callback_query(call.id, text=f"You pressed ❌ Not going")
        not_go(call)
    elif call.data == 'Not_sure':
        bot.answer_callback_query(call.id, text=f"You pressed 💭 Not sure")
        not_sure(call)
    elif call.data == 'Add':
        bot.answer_callback_query(call.id, text=f"You pressed ➕ Add")
        add(call)
    elif call.data == 'Sub':
        bot.answer_callback_query(call.id, text=f"You pressed ➖ Sub")
        sub(call)
    elif call.data == 'Sub_all':
        bot.answer_callback_query(call.id, text=f"You pressed ➖ Sub all")
        sub_all(call)
    elif call.data == 'Go_keeper':
        bot.answer_callback_query(call.id, text=f"You pressed ✅🥅 Going")
        go_event_keeper(call)
    elif call.data == 'Add_keeper':
        bot.answer_callback_query(call.id, text=f"You pressed ➕🥅 Add")
        add_keeper(call)
    elif call.data == 'Sub_keeper':
        bot.answer_callback_query(call.id, text=f"You pressed ➖🥅 Sub")
        sub_keeper(call)
