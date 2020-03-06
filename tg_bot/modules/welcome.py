import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler, run_async
from telegram.utils.helpers import mention_markdown, mention_html, escape_markdown

import tg_bot.modules.sql.welcome_sql as sql
from tg_bot import dispatcher, OWNER_ID, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin
from tg_bot.modules.helper_funcs.misc import build_keyboard, revert_buttons
from tg_bot.modules.helper_funcs.msg_types import get_welcome_type
from tg_bot.modules.helper_funcs.string_handling import markdown_parser, \
    escape_invalid_curly_brackets
from tg_bot.modules.log_channel import loggable

VALID_WELCOME_FORMATTERS = ['first', 'last', 'fullname', 'username', 'id', 'count', 'chatname', 'mention']

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}


# do not async
def send(update, message, keyboard, backup_message):
    try:
        msg = update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except IndexError:
        msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                  "\nنکته: پیغام فعلی  "
                                                                  "بخاطر مشکلات کد موشن قابل استفاده نیست "
                                                                  "ممکنه از قسمت اسم شخص باشه."),
                                                  parse_mode=ParseMode.MARKDOWN)
    except KeyError:
        msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                  "\nنکته:پیغام فعلی "
                                                                  "بخاطر بد جایگذاری دستورات قابل استفاده نیس "
                                                                  "لطفا دوباره چک کن!"),
                                                  parse_mode=ParseMode.MARKDOWN)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nنکته : دکمه ایی که طراحی کردی  "
                                                                      "لینکش ایراد داره لطفا چک کن."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nنکته: دکمه ایی که طراحی کردی"
                                                                      "شامل لینکی هست که تلگرام  "
                                                                      "ساپورت نمیکنه،لطفا چک کن."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nنکته: لینکی که وارد کردی خرابه. "
                                                                      "لطفا چک کن."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Could not parse! got invalid url host errors")
        else:
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nنکته : یه ارور ناشناخته ثبت شد برام "
                                                                      "لطفا دوباره چک کن."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.exception()

    return msg


@run_async
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    should_welc, cust_welcome, welc_type = sql.get_welc_pref(chat.id)
    if should_welc:
        sent = None
        new_members = update.effective_message.new_chat_members
        for new_mem in new_members:
            # Give the owner a special welcome
            if new_mem.id == OWNER_ID:
                update.effective_message.reply_text("امپراطور وارد میشود ،احترام بگذارید😍😚")
                continue

            # Don't welcome yourself
            elif new_mem.id == bot.id:
                continue

            else:
                # If welcome message is media, send with appropriate function
                if welc_type != sql.Types.TEXT and welc_type != sql.Types.BUTTON_TEXT:
                    ENUM_FUNC_MAP[welc_type](chat.id, cust_welcome)
                    return
                # else, move on
                first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.

                if cust_welcome:
                    if new_mem.last_name:
                        fullname = "{} {}".format(first_name, new_mem.last_name)
                    else:
                        fullname = first_name
                    count = chat.get_members_count()
                    mention = mention_markdown(new_mem.id, first_name)
                    if new_mem.username:
                        username = "@" + escape_markdown(new_mem.username)
                    else:
                        username = mention

                    valid_format = escape_invalid_curly_brackets(cust_welcome, VALID_WELCOME_FORMATTERS)
                    res = valid_format.format(first=escape_markdown(first_name),
                                              last=escape_markdown(new_mem.last_name or first_name),
                                              fullname=escape_markdown(fullname), username=username, mention=mention,
                                              count=count, chatname=escape_markdown(chat.title), id=new_mem.id)
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)
                else:
                    res = sql.DEFAULT_WELCOME.format(first=first_name)
                    keyb = []

                keyboard = InlineKeyboardMarkup(keyb)

                sent = send(update, res, keyboard,
                            sql.DEFAULT_WELCOME.format(first=first_name))  # type: Optional[Message]

        prev_welc = sql.get_clean_pref(chat.id)
        if prev_welc:
            try:
                bot.delete_message(chat.id, prev_welc)
            except BadRequest as excp:
                pass

            if sent:
                sql.set_clean_welcome(chat.id, sent.message_id)


@run_async
def left_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)
    if should_goodbye:
        left_mem = update.effective_message.left_chat_member
        if left_mem:
            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                update.effective_message.reply_text("☹️😢عشقم خدافظ")
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                ENUM_FUNC_MAP[goodbye_type](chat.id, cust_goodbye)
                return

            first_name = left_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if left_mem.last_name:
                    fullname = "{} {}".format(first_name, left_mem.last_name)
                else:
                    fullname = first_name
                count = chat.get_members_count()
                mention = mention_markdown(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape_markdown(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(cust_goodbye, VALID_WELCOME_FORMATTERS)
                res = valid_format.format(first=escape_markdown(first_name),
                                          last=escape_markdown(left_mem.last_name or first_name),
                                          fullname=escape_markdown(fullname), username=username, mention=mention,
                                          count=count, chatname=escape_markdown(chat.title), id=left_mem.id)
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = sql.DEFAULT_GOODBYE
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, res, keyboard, sql.DEFAULT_GOODBYE)


@run_async
@user_admin
def welcome(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    # if no args, show current replies.
    if len(args) == 0 or args[0].lower() == "noformat":
        noformat = args and args[0].lower() == "noformat"
        pref, welcome_m, welcome_type = sql.get_welc_pref(chat.id)
        update.effective_message.reply_text(
            "پیام خوش آمد این گروه تنظیم شده به: `{}`.\n*پیام خوش آمد "
            "({{}}):*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if welcome_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)

        else:
            if noformat:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m)

            else:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("روشن", "on"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text("آبرو داری میکنم!")

        elif args[0].lower() in ("خاموش", "off"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text("چشم ! من با کسی گرم نمیگیرم🙄")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("تو این دستور من فقط روشن/on یا خاموش/off رو میفهمم😶")


@run_async
@user_admin
def goodbye(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) == 0 or args[0] == "noformat":
        noformat = args and args[0] == "noformat"
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        update.effective_message.reply_text(
            "پیام خدافظی این گپ تنظیم شده به: `{}`.\n*پیام خدافظی "
            "({{}}) :*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        else:
            if noformat:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m)

            else:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("روشن", "on"):
            sql.set_gdbye_preference(str(chat.id), True)
            update.effective_message.reply_text("بله! هرموقع شخصی بخواد بره . همراهیش میکنم🤝")

        elif args[0].lower() in ("خاموش", "off"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text("دیگه رفتن کسی برام اهمیت نداره 😏")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("تو این دستور من فقط روشن/on یا خاموش/off رو میفهمم😶")


@run_async
@user_admin
@loggable
def set_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("لطفا بهم بگو چی میخوای بگم ؟")
        return ""

    sql.set_custom_welcome(chat.id, content or text, data_type, buttons)
    msg.reply_text("هر چیزی که شما بخواین رو میگم ")

    return "<b>{}:</b>" \
           "\n#متن_خوشامد" \
           "\n<b>توسط:</b> {}" \
           "\nتغییر کرد".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_welcome(chat.id, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text("پیام خوش آمد به اون چیزی که من میخوام بگم تغیر کرد!")
    return "<b>{}:</b>" \
           "\n#خوشامد_پیشفرض" \
           "\n<b>توسط:</b> {}" \
           "\nبه حالت پیشفرض تنظیم شد.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def set_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("لطفا بهم بگو چی میخوای بگم ؟")
        return ""

    sql.set_custom_gdbye(chat.id, content or text, data_type, buttons)
    msg.reply_text("وقتی که برن ، همین چیزی که خواستید رو بهشون میگم")
    return "<b>{}:</b>" \
           "\n#متن_خدافظی" \
           "\n<b>توسط:</b> {}" \
           "\nتغییر کرد.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text("پیام خدافظی با خودمه الان!")
    return "<b>{}:</b>" \
           "\n#خدافظی_پیشفرض" \
           "\n<b>توسط:</b> {}" \
           "\nبه حالت پیشفرض تنظیم شد.".format(html.escape(chat.title),
                                                 mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def clean_welcome(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            update.effective_message.reply_text("بهتره من پیامای خوشآمد دو روز پیشو پاک کنم.")
        else:
            update.effective_message.reply_text("من در حال حاضر خوش آمد ها رو پاک نمیکنم")
        return ""

    if args[0].lower() in ("روشن", "on"):
        sql.set_clean_welcome(str(chat.id), True)
        update.effective_message.reply_text("باش من سعی میکنم پیامای خوش آمد قدیمی تر رو پاک کنم")
        return "<b>{}:</b>" \
               "\n#خوشامدگویی_مرتب" \
               "\n<b>توسط:</b> {}" \
               "\nبه حالت <code>روشن</code> تغییر کرد.".format(html.escape(chat.title),
                                                                         mention_html(user.id, user.first_name))
    elif args[0].lower() in ("خاموش", "off"):
        sql.set_clean_welcome(str(chat.id), False)
        update.effective_message.reply_text("اوکی من پیامای خوش آمد رو پاک نمیکنم.")
        return "<b>{}:</b>" \
               "\n#خوشامدگویی_مرتب" \
               "\n<b>توسط:</b> {}" \
               "\nبه حالت <code>خاموش</code> تغییر کرد.".format(html.escape(chat.title),
                                                                          mention_html(user.id, user.first_name))
    else:
        # idek what you're writing, say yes or no
        update.effective_message.reply_text("تو این دستور من فقط روشن/on یا خاموش/off رو میفهمم😶")
        return ""


WELC_HELP_TXT = "پیام خوش آمد و خدافظی گپ شما میتونه به چندین حالت شخصی سازی بشه!" \
                " برای مثال تو میتونی *از این* کاراکتر ها داخل پیام خوش آمد و خدافظی استفاده کنی:\n" \
                " - `{{first}}`: این رو من به عنوان *اسم شخص* میشناسم\n" \
                " - `{{last}}`: این هم به عنوان *فامیلی* یا اسم دوم شخص میشناسم" \
                "اگه اسم دوم نداشته باشه ،اسم اولش رو مینویسم\n" \
                " - `{{fullname}}`:برام به عنوان *اسم کامل* تعریف شده. یعنی هم اسم اول هم دوم" \
                "اگه شخصی اسم دوم نداشته باشه فقط اسم اول رو مینویسم.\n" \
                " - `{{username}}`: تنظیم شده به عنوان آیدی کاربر . اگه طرف آیدی نداشته باشه" \
                "با یه منشن که اسم اولشو مینویسه معرفیش میکنم.\n" \
                " - `{{mention}}`: این منشن هست ،اسم کاربر که قابلیت لینک شدن به پروفایل رو داره.\n" \
                " - `{{id}}`: آیدی *عددی* کاربر رو نشون میده\n" \
                " - `{{count}}`: به شخص میگم که چندمین عضو گروه شده یا بوده.\n" \
                " - `{{chatname}}`: این کاراکتر *اسم گپ* رو نشون میده.\n" \
                "\nهرکدوم از کاراکتر ها باید داخل `{{}}` باشن تا توسط من شناسایی بشن.\n" \
                "پیام های احواس پرسی من همچنین از همه قابلیت های B/I/C/L پشتیبانی میکنه. " \
                "حتی کلید هم پشتیبانی میکنم . میتونی یه پیام خوش آمد باحال با کلید هام " \
                "درست کنی.\n" \
                "مثلا برای یه کلیک که قوانین گپ رو نشون بده ازین استفاده کنید: `[RULES](buttonurl://t.me/{}?start=group_id)`. " \
                "فقط کافیه `group_id` رو با آیدی عددی گپتون که میتونید با دستور /ID که داخل گپ میفرستید" \
                "و آیدی که بهتون میدم رو جایگزین کنید و کلید قوانین هم براتون تو پیام خوش آمد نشون میدم" \
                ".\n" \
                "اگه خوشتون میاد حتی میتونیدانواع مدیا ، ویس ، گیف و... برای اعضای جدید بفرستید " \
                "روی فایلتون ریپلی بزنید و دستور *تنظیم خوشامد* رو بنویسید.".format(dispatcher.bot.username)


@run_async
@user_admin
def welcome_help(bot: Bot, update: Update):
    update.effective_message.reply_text(WELC_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


# TODO: get welcome data from group butler snap
# def __import_data__(chat_id, data):
#     welcome = data.get('info', {}).get('rules')
#     welcome = welcome.replace('$username', '{username}')
#     welcome = welcome.replace('$name', '{fullname}')
#     welcome = welcome.replace('$id', '{id}')
#     welcome = welcome.replace('$title', '{chatname}')
#     welcome = welcome.replace('$surname', '{lastname}')
#     welcome = welcome.replace('$rules', '{rules}')
#     sql.set_custom_welcome(chat_id, welcome, sql.Types.TEXT)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    welcome_pref, _, _ = sql.get_welc_pref(chat_id)
    goodbye_pref, _, _ = sql.get_gdbye_pref(chat_id)
    return "پیام خوش آمد گپ شما: `{}`.\n" \
           "پیام خدافظی گپ شما: `{}`.".format(welcome_pref, goodbye_pref)


__help__ = """
میخوای آبرو داری کنم مهمون میاد؟ باشه هرجور صلاح میدونی😋

*فقط ادمینها:*
- [!خوشامد] (روشن یا خاموش) 
[/welcome] (on OR off) 👉 کلید خوشامدگویی من
——————————————————--
- [!خدافظی] (روشن یا خاموش)
[/goodbye] (on OR off) 👉 کلید خدافظی من
——————————————————--
-[!بگوخوشامد] (متن به همراه نماد ها)
[/setwelcome] (Text With Symbols) 👉 خوشامدگویی خاص 
——————————————————--
[!بگوخدافظی] (متن به همراه نماد ها)
[/setgoodbye] (Text With Symbols) 👉خداحافظی خاص
——————————————————-
[!صفرخوشامد]  [!صفرخدافظی]
[/resetwelcome]  , [/resetgoodbye]👉   پیشفرض
——————————————————--
[!خوشامدمرتب] (روشن یا خاموش)
[/cleanwelcome] (on OR off) 👇
پاک کردن پیام های خوشامد قدیمی تر 
——————————————————--
[!راهنماخوشامد] (P.V)
[/welcomehelp] (P.V) 👉 توضیحات نمادها
"""

__mod_name__ = "مهمون نواز🤵"

NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, new_member)
LEFT_MEM_HANDLER = MessageHandler(Filters.status_update.left_chat_member, left_member)
WELC_PREF_HANDLER = CommandHandler(["خوشامد", "welcome"], welcome, pass_args=True, filters=Filters.group)
GOODBYE_PREF_HANDLER = CommandHandler(["خدافظی", "goodbye"], goodbye, pass_args=True, filters=Filters.group)
SET_WELCOME = CommandHandler(["بگوخوشامد", "setwelcome"], set_welcome, filters=Filters.group)
SET_GOODBYE = CommandHandler(["بگوخدافظی", "setgoodbye"], set_goodbye, filters=Filters.group)
RESET_WELCOME = CommandHandler(["صفرخوشامد", "resetwelcome"], reset_welcome, filters=Filters.group)
RESET_GOODBYE = CommandHandler(["صفرخدافظی", "resetgoodbye"], reset_goodbye, filters=Filters.group)
CLEAN_WELCOME = CommandHandler(["خوشامدمرتب", "cleanwelcome"], clean_welcome, pass_args=True, filters=Filters.group)
WELCOME_HELP = CommandHandler(["راهنماخوشامد", "welcomehelp"], welcome_help)

dispatcher.add_handler(NEW_MEM_HANDLER)
dispatcher.add_handler(LEFT_MEM_HANDLER)
dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(CLEAN_WELCOME)
dispatcher.add_handler(WELCOME_HELP)
