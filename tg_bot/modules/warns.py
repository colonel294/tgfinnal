import html
import re
from typing import Optional, List

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery
from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, DispatcherHandlerStop, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, BAN_STICKER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, bot_admin, user_admin_no_reply, user_admin, \
    can_restrict
from tg_bot.modules.helper_funcs.extraction import extract_text, extract_user_and_text, extract_user
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.helper_funcs.string_handling import split_quotes
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = "<b>بخاطر گفتن کلمات زیر شما ممکنه اخطار  بگیری🚨:</b>\n"


# Not async
def warn(user: User, chat: Chat, reason: str, message: Message, warner: User = None) -> str:
    if is_user_admin(chat, user.id):
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "خودم😎"

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = "به علت رسیدن به {} اخطار، کاربر{} اخراج شد!".format(limit, mention_html(user.id, user.first_name))

        else:  # ban
            chat.kick_member(user.id)
            reply = "به علت رسیدن به {} اخطار، کاربر{} بن شد!".format(limit, mention_html(user.id, user.first_name))

        for warn_reason in reasons:
            reply += "\n - {}".format(html.escape(warn_reason))

        message.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        log_reason = "<b>{}:</b>" \
                     "\n#حذف_کاربر" \
                     "\n<b>مدیر:</b> {}" \
                     "\n<b>کاربر:</b> {} (<code>{}</code>)" \
                     "\n<b>به دلیل:</b> {}"\
                     "\n<b>تعداداخطار:</b> <code>{}/{}</code>".format(html.escape(chat.title),
                                                                  warner_tag,
                                                                  mention_html(user.id, user.first_name),
                                                                  user.id, reason, num_warns, limit)

    else:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("حذف اخطار", callback_data="rm_warn({})".format(user.id))]])

        reply = "{} تو {}/{} اخطار داری ... مراقب باش!".format(mention_html(user.id, user.first_name), num_warns,
                                                             limit)
        if reason:
            reply += "\nدلیل اخرین اخطاری که گرفتی:\n{}".format(html.escape(reason))

        log_reason = "<b>{}:</b>" \
                     "\n#اخطار" \
                     "\n<b>مدیر:</b> {}" \
                     "\n<b>کاربر:</b> {} (<code>{}</code>)" \
                     "\n<b>به دلیل:</b> {}"\
                     "\n<b>تعداداخطار:</b> <code>{}/{}</code>".format(html.escape(chat.title),
                                                                  warner_tag,
                                                                  mention_html(user.id, user.first_name),
                                                                  user.id, reason, num_warns, limit)

    try:
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False)
        else:
            raise
    return log_reason


@run_async
@user_admin_no_reply
@bot_admin
@loggable
def button(bot: Bot, update: Update) -> str:
    query = update.callback_query  # type: Optional[CallbackQuery]
    user = update.effective_user  # type: Optional[User]
    match = re.match(r"rm_warn\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat  # type: Optional[Chat]
        res = sql.remove_warn(user_id, chat.id)
        if res:
            update.effective_message.edit_text(
                "اخطار ها توسط {} پاک شد!.".format(mention_html(user.id, user.first_name)),
                parse_mode=ParseMode.HTML)
            user_member = chat.get_member(user_id)
            return "<b>{}:</b>" \
                   "\n#پاکسازی_اخطار" \
                   "\n<b>توسط:</b> {}" \
                   "\n<b>کاربر:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                mention_html(user.id, user.first_name),
                                                                mention_html(user_member.user.id, user_member.user.first_name),
                                                                user_member.user.id)
        else:
            update.effective_message.edit_text(
                "این کاربر اخطاری نداره که".format(mention_html(user.id, user.first_name)),
                parse_mode=ParseMode.HTML)

    return ""


@run_async
@user_admin
@can_restrict
@loggable
def warn_user(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    warner = update.effective_user  # type: Optional[User]

    user_id, reason = extract_user_and_text(message, args)

    if user_id:
        if message.reply_to_message and message.reply_to_message.from_user.id == user_id:
            return warn(message.reply_to_message.from_user, chat, reason, message.reply_to_message, warner)
        else:
            return warn(chat.get_member(user_id).user, chat, reason, message, warner)
    else:
        message.reply_text("اومم نشونم بدش🤨")
    return ""


@run_async
@user_admin
@bot_admin
@loggable
def reset_warns(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    user_id = extract_user(message, args)

    if user_id:
        sql.reset_warns(user_id, chat.id)
        message.reply_text("اخطار ها صفر شد!")
        warned = chat.get_member(user_id).user
        return "<b>{}:</b>" \
               "\n#ریست_اخطار" \
               "\n<b>توسط:</b> {}" \
               "\n<b>کاربر:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name),
                                                            mention_html(warned.id, warned.first_name),
                                                            warned.id)
    else:
        message.reply_text("آیدیش تو دیتابیس من موجود نیست!")
    return ""


@run_async
def warns(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = "این شیطون  {}/{} اخطار داره ، و دلایلش هم :".format(num_warns, limit)
            for reason in reasons:
                text += "\n - {}".format(reason)

            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                "این شیطون {}/{} اخطار داره ولی دلیل خاصی براشون تعریف نشده.".format(num_warns, limit))
    else:
        update.effective_message.reply_text("رفیقمون پاک پاکه!")


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) >= 2:
        # set trigger -> lower, so as to avoid adding duplicate filters with different cases
        keyword = extracted[0].lower()
        content = extracted[1]

    else:
        return

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text("کلمه/جمله *{}* جزو کلمات ممنوعه ثبت شد!".format(keyword))
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat.id)

    if not chat_filters:
        msg.reply_text("هنوز کلمه/جمله ممنوعه برام ثبت نشده")
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat.id, to_remove)
            msg.reply_text("چشم قربان ،من دیگه مردم رو برای این موضوع دستگیر نمیکنم👮🏻‍♂️")
            raise DispatcherHandlerStop

    msg.reply_text("میبخشید داخل پرونده ها این کلمه/جمله رو نمیبینم /warnlist رو چک کن👮🏻‍♂️")


@run_async
def list_warn_filters(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_warn_triggers(chat.id)

    if not all_handlers:
        update.effective_message.reply_text("هنوز کلمه/جمله ممنوعه برام ثبت نشده")
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = " - {}\n".format(html.escape(keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)
            filter_list = entry
        else:
            filter_list += entry

    if not filter_list == CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)


@run_async
@loggable
def reply_filter(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user  # type: Optional[User]
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, chat, warn_filter.reply, message)
    return ""


@run_async
@user_admin
@loggable
def set_warn_limit(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text(" کمترین مقدار برای اخطار قبل از اخراج 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text("تعداد اخطار ها به {} تنظیم شد!".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#تنظیم_حداخطار" \
                       "\n<b>توسط:</b> {}" \
                       "\nبه تعداد <code>{}</code> اخطار تغییر کرد".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name), args[0])
        else:
            msg.reply_text("یه عدد انگلیسی بهم بده !")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)

        msg.reply_text("درحال حاظر حداخطار {} هست".format(limit))
    return ""


@run_async
@user_admin
def set_warn_strength(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].lower() in ("روشن", "on"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("وقتی اخطار ها زیاد بشن . مقصر هاشون از گروه بن میشن!")
            return "<b>{}:</b>\n" \
                   "<b>توسط:</b> {}\n" \
                   "حالت بیرحمی روشن شد! کاربرهای مقصر از گپ بن خواهند شد".format(html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))

        elif args[0].lower() in ("خاموش", "off"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text("وقتی اخطار هاشون زیاد بشه ، از گپ کیک میشن! ولی باز میتونن اگه بخوان به گروه برگردن.")
            return "<b>{}:</b>\n" \
                   "<b>توسط:</b> {}\n" \
                   "حالت بیرحمی خاموش شد! کاربرهای مقصر فقط اخراج خواهند شد".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        else:
            msg.reply_text("توی حالت بیرحمی فقط میتونی به من دستورات on/روشن یا off/خاموش رو بدی😶")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text("من بیرحم نیستم! اخطارهای شخصی به حدش برسه فقط اخراج میشه😊",
                           parse_mode=ParseMode.MARKDOWN)
        else:
            msg.reply_text("من بیرحمم ! اخطار های شخصی به حدش برسه بنش میکنم😡",
                           parse_mode=ParseMode.MARKDOWN)
    return ""


def __stats__():
    return "{} فیلتر اخطار در {} گپ.\n" \
           "{} فیلتر اخراج {} گپ.".format(sql.num_warns(), sql.num_warn_chats(),
                                                      sql.num_warn_filters(), sql.num_warn_filter_chats())


def __import_data__(chat_id, data):
    for user_id, count in data.get('warns', {}).items():
        for x in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return "این گپ {} تا فیلتر اخطار داره. اگه کسی{} اخطار بگیره" \
           "از گروه *{}* میشه.".format(num_warn_filters, limit, "اخراج" if soft_warn else "بن")


__help__ = """
بحث غیرمجاز شد دستگیرشون کنم؟ هرطور شما دستور بدی 👮🏻‍♂️

- [!اخطارها] (آیدی) (ریپلی)
[/warns] (ID) (Reply) 👉 تعداد اخطار و دلایل
——————————————————--
- [!اخطارنامه] 
[/warnlist] 👉 لیست کلمات/جملات ممنوعه
——————————————————--
*فقط ادمین ها*
[!اخطار] (آیدی) (ریپلی)
[/warn] (ID) (Reply) 👉 اخطار شخصی
——————————————————--
- [!اخطار0] (آیدی) (ریپلی)
[/resetwarn] (ID) (Reply) 👉 صفرکردن اخطار
———————————————————
- [!اخطاربده] ("کلمه/جمله") (دلیل)
[/addwarn] (Text) (Reason) 👇
کلمه یا جمله رو ببینم اخطار میدم 🚨 *قسمت دلیل الزامی*
——————————————————----
- [!اخطارنده] (کلمه/جمله) 
[/stopwarn] (Text) 👉 آزاد کردن کلمه/جمله ممنوعه
———————————————————-
- [!حداخطار] (عدد)
[/warnlimit] (INT) 👉 تنظیم حداخطار
———————————————————--
- [!بیرحمی] (روشن یا خاموش)
[/warnstrength] (on OR off) 👇
روشن : رسیدن به حد اخطار به معنای بن
خاموش : رسیدن به حد اخطار به معنای اخراج
"""

__mod_name__ = "اخطارنامه📝"

WARN_HANDLER = CommandHandler(["اخطار", "warn"], warn_user, pass_args=True, filters=Filters.group)
RESET_WARN_HANDLER = CommandHandler(["اخطار0", "resetwarns"], reset_warns, pass_args=True, filters=Filters.group)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button, pattern=r"rm_warn")
MYWARNS_HANDLER = DisableAbleCommandHandler(["اخطارها", "warns"], warns, pass_args=True, filters=Filters.group)
ADD_WARN_HANDLER = CommandHandler(["اخطاربده", "addwarn"], add_warn_filter, filters=Filters.group)
RM_WARN_HANDLER = CommandHandler(["اخطارنده", "stopwarn"], remove_warn_filter, filters=Filters.group)
LIST_WARN_HANDLER = DisableAbleCommandHandler(["اخطارنامه", "warnlist"], list_warn_filters, filters=Filters.group, admin_ok=True)
WARN_FILTER_HANDLER = MessageHandler(CustomFilters.has_text & Filters.group, reply_filter)
WARN_LIMIT_HANDLER = CommandHandler(["حداخطار", "warnlimit"], set_warn_limit, pass_args=True, filters=Filters.group)
WARN_STRENGTH_HANDLER = CommandHandler(["بیرحمی", "warnstrength"], set_warn_strength, pass_args=True, filters=Filters.group)

dispatcher.add_handler(WARN_HAN-DLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
