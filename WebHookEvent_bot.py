import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import logging
from datetime import datetime

# Настройка логирования для Yandex Cloud
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Telegram Access
token = os.getenv('token')
bot = telebot.TeleBot(token, threaded=False)


# Функция для отправки логов в админский чат
def send_log_to_admin(message_text):
    """Отправляет лог в админский чат с HTML-разметкой"""
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not admin_chat_id:
        log_entry = {
            "type": "admin_log_error",
            "timestamp": timestamp,
            "error": "ADMIN_CHAT_ID not set",
            "message_preview": message_text[:200]
        }
        logger.warning(json.dumps(log_entry, ensure_ascii=False))
        return False

    try:
        admin_chat_id_int = int(admin_chat_id)
        sent_message = bot.send_message(
            admin_chat_id_int,
            f"[LOG] {message_text}",
            parse_mode="HTML"
        )
        log_entry = {
            "type": "admin_log_sent",
            "timestamp": timestamp,
            "admin_chat_id": admin_chat_id_int,
            "message_id": sent_message.message_id,
            "message_preview": message_text[:200],
            "status": "success"
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
        return True
    except ValueError:
        log_entry = {
            "type": "admin_log_error",
            "timestamp": timestamp,
            "error": f"ADMIN_CHAT_ID is not a valid integer: {admin_chat_id}",
            "error_type": "ValueError",
            "message_preview": message_text[:200]
        }
        logger.error(json.dumps(log_entry, ensure_ascii=False))
        return False
    except telebot.apihelper.ApiTelegramException as e:
        log_entry = {
            "type": "admin_log_error",
            "timestamp": timestamp,
            "error": str(e),
            "error_code": getattr(e, 'error_code', None),
            "error_type": "ApiTelegramException",
            "admin_chat_id": admin_chat_id_int if 'admin_chat_id_int' in locals() else admin_chat_id,
            "message_preview": message_text[:200]
        }
        logger.error(json.dumps(log_entry, ensure_ascii=False))
        if "chat not found" in str(e).lower():
            logger.error(json.dumps({
                "type": "admin_log_diagnostic",
                "timestamp": timestamp,
                "diagnostic": "Chat not found. Check that ADMIN_CHAT_ID is correct and bot is a member of this chat",
                "admin_chat_id": admin_chat_id_int if 'admin_chat_id_int' in locals() else admin_chat_id
            }, ensure_ascii=False))
        elif "forbidden" in str(e).lower():
            logger.error(json.dumps({
                "type": "admin_log_diagnostic",
                "timestamp": timestamp,
                "diagnostic": "Bot is forbidden to send message. Check bot permissions in this chat",
                "admin_chat_id": admin_chat_id_int if 'admin_chat_id_int' in locals() else admin_chat_id
            }, ensure_ascii=False))
        return False
    except Exception as e:
        log_entry = {
            "type": "admin_log_error",
            "timestamp": timestamp,
            "error": str(e),
            "error_type": type(e).__name__,
            "admin_chat_id": admin_chat_id,
            "message_preview": message_text[:200]
        }
        logger.error(json.dumps(log_entry, ensure_ascii=False), exc_info=True)
        return False


# Функция для логирования действий пользователя
def log_user_action(user, action, call_data=None, additional_info=None, chat=None):
    """Логирует действие и отправляет админу HTML-сообщение с именем чата"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Получаем название чата
    chat_title = "Private"
    if chat:
        if hasattr(chat, 'title') and chat.title:
            chat_title = chat.title
        elif hasattr(chat, 'first_name') and chat.first_name:
            chat_title = chat.first_name
    chat_info = f"Chat: {chat_title}"

    # HTML-ссылка на пользователя
    user_link = parse_html(user)

    log_entry = {
        "timestamp": timestamp,
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "action": action,
        "callback_data": call_data,
        "additional_info": additional_info,
        "chat_title": chat_title
    }
    logger.info(json.dumps(log_entry, ensure_ascii=False))

    # Формируем читаемое сообщение для админа (HTML)
    msg = f"{user_link}\nAction: {action}"
    if call_data:
        msg += f"\nButton: {call_data}"
    if additional_info:
        msg += f"\nInfo: {additional_info}"
    msg += f"\n{chat_info}"

    send_log_to_admin(msg)
    return log_entry


# Parser HTML
def parse_html(user):
    tg_id = user.id
    name = user.full_name
    html_text = f'<a href="tg://user?id={tg_id}">{name}</a>'
    return html_text


# Cloud Function Handler
def handler(event, context):
    logger.info(json.dumps({"type": "request_received", "event": event}))

    try:
        body = json.loads(event['body'])
        update = telebot.types.Update.de_json(body)

        if update.message:
            chat_id = update.message.chat.id
            thread_id = getattr(update.message, 'message_thread_id', None)
            logger.info(json.dumps({
                "type": "update_info",
                "chat_id": chat_id,
                "thread_id": thread_id,
                "message_type": "message"
            }))
        elif update.callback_query:
            chat_id = update.callback_query.message.chat.id
            thread_id = getattr(update.callback_query.message, 'message_thread_id', None)
            logger.info(json.dumps({
                "type": "update_info",
                "chat_id": chat_id,
                "thread_id": thread_id,
                "message_type": "callback_query"
            }))

        bot.process_new_updates([update])
        logger.info(json.dumps({"type": "success", "message": "Update processed successfully"}))

    except Exception as e:
        logger.error(json.dumps({"type": "error", "error": str(e)}), exc_info=True)
        raise

    return {
        'statusCode': 200,
        'body': json.dumps('OK')
    }


# Функция для отправки сообщения с поддержкой тем
def send_message_with_thread(chat_id, text, thread_id=None, reply_markup=None, parse_mode="HTML"):
    try:
        if thread_id:
            return bot.send_message(chat_id, text, message_thread_id=thread_id,
                                    reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(json.dumps({"type": "send_error", "error": str(e)}))
        raise


# Start
@bot.message_handler(commands=['start'])
def start_helper(message) -> None:
    thread_id = getattr(message, 'message_thread_id', None)
    log_user_action(message.from_user, "START_COMMAND",
                    additional_info=f"Chat: {message.chat.id}, Thread: {thread_id}",
                    chat=message.chat)
    start_message = "I'm a bot to organize events. Print /event EVENT NAME to create event\n"
    send_message_with_thread(message.chat.id, start_message, thread_id)


# Help
@bot.message_handler(commands=['help'])
def helper(message) -> None:
    thread_id = getattr(message, 'message_thread_id', None)
    log_user_action(message.from_user, "HELP_COMMAND",
                    additional_info=f"Chat: {message.chat.id}, Thread: {thread_id}",
                    chat=message.chat)
    help_message = 'Print "/event" EVENT NAME to create event\nPrint "/start" to get start message\n' \
                   'Print /description to get description (in Russian)'
    send_message_with_thread(message.chat.id, help_message, thread_id)


# Description
@bot.message_handler(commands=['description'])
def description(message) -> None:
    thread_id = getattr(message, 'message_thread_id', None)
    log_user_action(message.from_user, "DESCRIPTION_COMMAND",
                    additional_info=f"Chat: {message.chat.id}, Thread: {thread_id}",
                    chat=message.chat)
    description_message = "Для создания опроса введите команду '/event', " \
                          "указав название этого опроса.\n" \
                          "Кнопка ✅ Going добавит вас в список тех, кто идет.\n" \
                          "Кнопка ❌ Not going добавит вас в список тех, кто идет.\n" \
                          "Кнопка 💭 Not sure добавит вас в список тех, кто идет.\n" \
                          "При нажатии кнопки Add ваш + будет добавлен в список, то есть количество " \
                          "людей, которые придут с вами.\n" \
                          "При нажатии кнопки Sub будет убран 1 ваш +.\n" \
                          "При нажатии кнопки Sub all будут убраны все ваши +.\n"
    send_message_with_thread(message.chat.id, description_message, thread_id)


# Event
@bot.message_handler(commands=['event'])
def create_event(message) -> None:
    thread_id = message.message_thread_id
    chat_id = message.chat.id

    if len(message.text.split()) == 1:
        name = '👉   No name event   👈\n'
    else:
        name = '👉   ' + ' '.join(message.text.split()[1:]) + '   👈\n'

    text = ("Going😀:\n"
            "Not going😐:\n"
            "Not sure🤔:\n"
            "Total going:\n"
            "✅:\n"
            "➕:\n"
            "❌:\n"
            "💭:")

    sent_msg = send_message_with_thread(
        chat_id=chat_id,
        text=name + text,
        thread_id=thread_id,
        reply_markup=base_keyboard(),
        parse_mode="HTML"
    )

    log_user_action(
        message.from_user, "CREATE_EVENT_COMMAND",
        additional_info=f"Chat: {chat_id}, Thread: {thread_id}, Event:\n {name}MessageID: {sent_msg.message_id}",
        chat=message.chat
    )


# Keyboard layouts
def base_keyboard():
    keyboard = InlineKeyboardMarkup()
    key_change_state = InlineKeyboardButton(text="Close event", callback_data="change_state")
    key_go = InlineKeyboardButton(text="✅ Going ", callback_data="Go")
    key_not_go = InlineKeyboardButton(text="❌ Not going", callback_data="Not_go")
    key_not_sure = InlineKeyboardButton(text="💭 Not sure", callback_data='Not_sure')
    key_add = InlineKeyboardButton(text="➕ Add ", callback_data='Add')
    key_sub = InlineKeyboardButton(text="➖ Sub", callback_data='Sub')
    key_sub_all = InlineKeyboardButton(text="➖ Sub all", callback_data='Sub_all')
    keyboard.row(key_change_state)
    keyboard.row(key_go, key_not_go, key_not_sure)
    keyboard.row(key_add, key_sub, key_sub_all)
    return keyboard

def closed_keyboard():
    keyboard = InlineKeyboardMarkup()
    key_change_state = InlineKeyboardButton(text="Open event", callback_data="change_state")
    key_not_go = InlineKeyboardButton(text="❌ Not going", callback_data="Not_go")
    key_sub = InlineKeyboardButton(text="➖ Sub", callback_data='Sub')
    key_sub_all = InlineKeyboardButton(text="➖ Sub all", callback_data='Sub_all')
    keyboard.row(key_change_state)
    keyboard.row(key_not_go)
    keyboard.row(key_sub, key_sub_all)
    return keyboard


# Change state
def change_state(call) -> None:
    log_user_action(call.from_user, "CHANGE_STATE", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}, Chat: {call.message.chat.id}",
                    chat=call.message.chat)

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
        bot.edit_message_text(text_message, call.message.chat.id, call.message.id, reply_markup=keyboard,
                              parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, text="You no permission to open or close event")


# Count people
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
            going_plus += int(pos[1:pos.index(", from:")])
    temp[-5] = f"Total going: {going + going_plus}"
    temp[-4] = f"✅: {going}"
    temp[-3] = f"➕: {going_plus}"
    temp[-2] = f"❌: {not_going}"
    temp[-1] = f"💭: {in_doubt}"
    text_message = "\n".join(m for m in temp)
    try:
        bot.edit_message_text(text_message, call.message.chat.id, call.message.id, reply_markup=keyboard,
                              parse_mode="HTML")
    except Exception as e:
        logger.error(json.dumps({"type": "count_error", "error": str(e)}))


# Press helper
def press(call):
    text_message = call.message.html_text
    message = parse_html(call.from_user)
    if text_message[:16] != "❌ EVENT CLOSED ❌":
        keyboard = base_keyboard()
    else:
        keyboard = closed_keyboard()
    temp = text_message.split("\n")
    return message, keyboard, temp


# Add to message
def add_to_message(temp, index, message, mind) -> str:
    if mind != "✅":
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    else:
        plus_list = []
        for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
            if "➕" in people:
                plus_list.append(temp.pop(temp.index(people)))
        start_text = "\n".join(m for m in temp[:temp.index(index)]) + '\n'
        if plus_list:
            end_text = "\n" + "\n".join(m for m in plus_list) + "\n" + "\n".join(m for m in temp[temp.index(index):])
        else:
            end_text = "\n" + "\n".join(m for m in temp[temp.index(index):])
        text_message = start_text + mind + ' ' + message + end_text
    return text_message


# Go event
def go_event(call) -> None:
    log_user_action(call.from_user, "GO_EVENT", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

    message, keyboard, temp = press(call)
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❌ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('💭 ' + message))
    if '✅ ' + message in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not going😐:", message, '✅')
        count_people(call, text_message, keyboard)


# Not go
def not_go(call) -> None:
    log_user_action(call.from_user, "NOT_GO", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

    message, keyboard, temp = press(call)
    if '✅ ' + message in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        temp.pop(temp.index('💭 ' + message))
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        pass
    else:
        text_message = add_to_message(temp, "Not sure🤔:", message, '❌')
        count_people(call, text_message, keyboard)


# Not sure
def not_sure(call) -> None:
    log_user_action(call.from_user, "NOT_SURE", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

    message, keyboard, temp = press(call)
    if '✅ ' + message in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        temp.pop(temp.index('✅ ' + message))
    if '❌ ' + message in temp[temp.index("Not going😐:"):temp.index("Not sure🤔:")]:
        temp.pop(temp.index('❌ ' + message))
    if '💭 ' + message in temp[temp.index("Not sure🤔:"):-5]:
        pass
    else:
        text_message = add_to_message(temp, temp[-5], message, '💭')
        count_people(call, text_message, keyboard)


# Add plus
def add(call) -> None:
    log_user_action(call.from_user, "ADD_PLUS", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

    message, keyboard, temp = press(call)
    text_message = call.message.html_text
    found = False
    for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            number = int(people[1:people.index(", from:")]) + 1
            temp[temp.index(people)] = f"➕{number}, from: {message}"
            text_message = "\n".join(m for m in temp)
            found = True
            break

    if not found:
        text_message = add_to_message(temp, "Not going😐:", message, f'➕1, from:')

    count_people(call, text_message, keyboard)


# Sub plus
def sub(call) -> None:
    log_user_action(call.from_user, "SUB_PLUS", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

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
            break


# Sub all
def sub_all(call) -> None:
    log_user_action(call.from_user, "SUB_ALL_PLUS", call_data=call.data,
                    additional_info=f"Message ID: {call.message.id}",
                    chat=call.message.chat)

    message, keyboard, temp = press(call)
    for people in temp[temp.index("Going😀:"):temp.index("Not going😐:")]:
        if ("➕" in people) and (message in people):
            temp.pop(temp.index(people))
            text_message = "\n".join(m for m in temp)
            count_people(call, text_message, keyboard)
            break


# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "change_state":
        change_state(call)
        bot.answer_callback_query(call.id, text="State changed")
    elif call.data == 'Go':
        bot.answer_callback_query(call.id, text="You pressed ✅ Going")
        go_event(call)
    elif call.data == 'Not_go':
        bot.answer_callback_query(call.id, text="You pressed ❌ Not going")
        not_go(call)
    elif call.data == 'Not_sure':
        bot.answer_callback_query(call.id, text="You pressed 💭 Not sure")
        not_sure(call)
    elif call.data == 'Add':
        bot.answer_callback_query(call.id, text="You pressed ➕ Add")
        add(call)
    elif call.data == 'Sub':
        bot.answer_callback_query(call.id, text="You pressed ➖ Sub")
        sub(call)
    elif call.data == 'Sub_all':
        bot.answer_callback_query(call.id, text="You pressed ➖ Sub all")
        sub_all(call)

# set webhook: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_HTTPS_URL>