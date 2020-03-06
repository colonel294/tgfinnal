import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, LOGGER
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_admin, can_restrict
from tg_bot.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.log_channel import loggable


@run_async
@bot_admin
@user_admin
@loggable
def mute(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("یا برام آیدیش رو بنویس یا روش ریپلی بزن تا ساکتش کنم برات.")
        return ""

    if user_id == bot.id:
        message.reply_text("من خفه نمیشم☺️")
        return ""

    member = chat.get_member(int(user_id))

    if member:
        if is_user_admin(chat, user_id, member=member):
            message.reply_text("حقیقتا من با ادمینا در نمیوفتم!")

        elif member.can_send_messages is None or member.can_send_messages:
            bot.restrict_chat_member(chat.id, user_id, can_send_messages=False)
            message.reply_text("🤐")
            return "<b>{}:</b>" \
                   "\n#سکوت" \
                   "\n<b>توسط:</b> {}" \
                   "\n<b>به شخص:</b> {}".format(html.escape(chat.title),
                                              mention_html(user.id, user.first_name),
                                              mention_html(member.user.id, member.user.first_name))

        else:
            message.reply_text("عه ایشون که از قبل تو بنده ماس!")
    else:
        message.reply_text("تو ممبرا نیس که،فرار نکرده؟")

    return ""


@run_async
@bot_admin
@user_admin
@loggable
def unmute(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("ای جانم😄 خوب یا آیدیش رو بده یا روش ریپلی بزن تا آزادش کنم")
        return ""

    member = chat.get_member(int(user_id))

    if member:
        if is_user_admin(chat, user_id, member=member):
            message.reply_text("حاجی مشکوک میزنی، ادمینه که😬 ")
            return ""

        elif member.status != 'kicked' and member.status != 'left':
            if member.can_send_messages and member.can_send_media_messages \
                    and member.can_send_other_messages and member.can_add_web_page_previews:
                message.reply_text("این تو بند ما نیس ! احتمالا قبلا آزاد شده")
                return ""
            else:
                bot.restrict_chat_member(chat.id, int(user_id),
                                         can_send_messages=True,
                                         can_send_media_messages=True,
                                         can_send_other_messages=True,
                                         can_add_web_page_previews=True)
                message.reply_text("بزن دست قشنگروو، ایشالله آزادی همتون")
                return "<b>{}:</b>" \
                       "\n#حذف_سکوت" \
                       "\n<b>توسط:</b> {}" \
                       "\n<b>به شخص:</b> {}".format(html.escape(chat.title),
                                                  mention_html(user.id, user.first_name),
                                                  mention_html(member.user.id, member.user.first_name))
    else:
        message.reply_text("این شخص اصلا تو گپ نیس چه برسه تو بند باشه😰")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def temp_mute(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("زیاد متوجه نشدم . کیو میگی؟.")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("نمیتونم پیداش کنم!")
            return ""
        else:
            raise

    if is_user_admin(chat, user_id, member):
        message.reply_text("روزی که بتونم یه ادمینو ساکت کنم اون روز شیرینی میدم.")
        return ""

    if user_id == bot.id:
        message.reply_text("من خفه بشو نیستم")
        return ""

    if not reason:
        message.reply_text("اگه میخوای یه مدت آب خنک بخوره زمانشم بگو")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    mutetime = extract_time(message, time_val)

    if not mutetime:
        return ""

    log = "<b>{}:</b>" \
          "\n#سکوت موقت:" \
          "\n<b>توسط:</b> {}" \
          "\n<b>شخص:</b> {}" \
          "\n<b>به مدت:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name), time_val)
    if reason:
        log += "\n<b>به دلیل:</b> {}".format(reason)

    try:
        if member.can_send_messages is None or member.can_send_messages:
            bot.restrict_chat_member(chat.id, user_id, until_date=mutetime, can_send_messages=False)
            message.reply_text("به مدت {}:🤐!".format(time_val))
            return log
        else:
            message.reply_text("عه ایشون که از قبل تو بنده ماس!")

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text("به مدت {}:🤐!".format(time_val), quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR muting user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("نمیتونم😕 فک کنم گردنش کلفته")

    return ""


__help__ = """
گاهی اوقات سکوت بهترین انتخاب برای یه فرد عاقل است🤫
یا اصلا بزور ساکتش میکنم🤪
*فقط ادمین ها* 
- [!سایلنت] (ریپلی) ( آیدی)
[/silent] (Reply) (ID)👉 سکوت دائم 
———————————————————--
- [!آزاد] (ریپلی) (آیدی) 
[/unmute] (Reply) (ID)👉 حذف سکوت
———————————————————--
- [!سکوت] (ریپلی یا آیدی) (زمان)
[/mute] (Reply OR ID) (Time)👉
سکوت زماندار
———————————————————--
1: در سکوت زمان دار پسوند زمان چسبیده به عدد وارد شه لطفا
2: پسوند های زمان شامل m=دقیقه ، h=ساعت و d=روز
مثال : 
/mute @admin 2h
"""

__mod_name__ = "سکوت🤫"

MUTE_HANDLER = CommandHandler(["سایلنت", "silnet"], mute, pass_args=True, filters=Filters.group)
UNMUTE_HANDLER = CommandHandler(["آزاد", "unmute"], unmute, pass_args=True, filters=Filters.group)
TEMPMUTE_HANDLER = CommandHandler(["سکوت", "mute"], temp_mute, pass_args=True, filters=Filters.group)

dispatcher.add_handler(MUTE_HANDLER)
dispatcher.add_handler(UNMUTE_HANDLER)
dispatcher.add_handler(TEMPMUTE_HANDLER)
