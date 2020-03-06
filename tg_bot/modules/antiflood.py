import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import antiflood_sql as sql

FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(bot: Bot, update: Update) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        chat.kick_member(user.id)
        msg.reply_text("من همرو دوست دارم . ولی توو ، تو فقط باعث ناامیدی گونه بشریتی  "
                       "گمشو بیرون😒.")

        return "<b>{}:</b>" \
               "\n#بن_شد" \
               "\n<b>کاربر:</b> {}" \
               "\nاسپم داخل گپ.".format(html.escape(chat.title),
                                             mention_html(user.id, user.first_name))

    except BadRequest:
        msg.reply_text("من نمیتونم کسیو بیرون کنم اینجا .اجازشو ندارم! پس تا اونموقع حالت ضد تکرار خاموش.")
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#اطلاعات" \
               "\nاجازه اخراج کسیو ندارم ، تا اونموقع ضد تکرار خاموش.".format(chat.title)


@run_async
@user_admin
@can_restrict
@loggable
def set_flood(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "خاموش" or val == "off" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text("مسلسل خاموش")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text("مسلسل خاموش")
                return "<b>{}:</b>" \
                       "\n#ضدتکرار" \
                       "\n<b>توسط:</b> {}" \
                       "\nخاموش شد.".format(html.escape(chat.title), mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text("حالت ضد تکرار یا باید 0 باشه یا یه عددی بزرگ تر از 3")
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text("حالت ضد تکرار آبدیت شد و بعد از {} تکرار ،اخراج".format(amount))
                return "<b>{}:</b>" \
                       "\n#ضدتکرار" \
                       "\n<b>توسط:</b> {}" \
                       "\nتنظیم شد به <code>{}</code> پیام متوالی.".format(html.escape(chat.title),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text("متوجه نشدم . یا دستور خاموش یا یه عدد برای تنظیمش بفرست.")

    return ""


@run_async
def flood(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        update.effective_message.reply_text("من در حال حاضر میزان تکرار رو کنترل نمیکنم")
    else:
        update.effective_message.reply_text(
            "حالت ضد تکرار من فعاله و کسانی که بیش از {} پیام متوالی بفرستن اخراج میشن!.".format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "در حال حاضر سکان این قابلیت دستم نیس!"
    else:
        return "حد تکرار یه پیام تو این گپ {} هست!".format(limit)


__help__ = """
گپ مورد حمله قرار میگیره؟ اسپمرها 
همیشه گپو میبندن به رگبار
من سنگرت میشم فرمانده💂‍♀️

- [!مسلسل] 
[/flood] 👉 تعداد و وضعیت حد
———————————————————--
*فقط ادمین ها* 
- [!ضدتکرار] (خاموش و 0) یا (عدد)
[/setflood] (off & 0) OR (INT) 👉
کلید ضدتکرار
———————————————————--
"""

__mod_name__ = "مسلسل"

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update & Filters.group, check_flood)
SET_FLOOD_HANDLER = CommandHandler(["ضدتکرار", "setflood"], set_flood, pass_args=True, filters=Filters.group)
FLOOD_HANDLER = CommandHandler(["مسلسل", "flood"], flood, filters=Filters.group)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)
