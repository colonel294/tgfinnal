import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin, can_delete
from tg_bot.modules.log_channel import loggable


@run_async
@user_admin
@loggable
def purge(bot: Bot, update: Update, args: List[str]) -> str:
    msg = update.effective_message  # type: Optional[Message]
    if msg.reply_to_message:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        if can_delete(chat, bot.id):
            message_id = msg.reply_to_message.message_id
            if args and args[0].isdigit():
                delete_to = message_id + int(args[0])
            else:
                delete_to = msg.message_id - 1
            for m_id in range(delete_to, message_id - 1, -1):  # Reverse iteration over message ids
                try:
                    bot.deleteMessage(chat.id, m_id)
                except BadRequest as err:
                    if err.message == "Message can't be deleted":
                        bot.send_message(chat.id, "ببخشید😢 .نمیتونم همه پیامارو پاک کنم ، شاید پیام قدیمیه🧐 "
                                                  "یا شاید من اجازشو ندارم.")

                    elif err.message != "Message to delete not found":
                        LOGGER.exception("Error while purging chat messages.")

            try:
                msg.delete()
            except BadRequest as err:
                if err.message == "Message can't be deleted":
                    bot.send_message(chat.id, "ببخشید😢 .نمیتونم همه پیامارو پاک کنم ، شاید پیام قدیمیه🧐 "
                                              "یا شاید من اجازشو ندارم..")

                elif err.message != "Message to delete not found":
                    LOGGER.exception("Error while purging chat messages.")

            bot.send_message(chat.id, "پیامارو سوزوندم فرمانده😎.")
            return "<b>{}:</b>" \
                   "\n#پاکسازی" \
                   "\n<b>توسط:</b> {}" \
                   "\nتعداد <code>{}</code> پیام.".format(html.escape(chat.title),
                                                               mention_html(user.id, user.first_name),
                                                               delete_to - message_id)

    else:
        msg.reply_text("اومم رو یه پیام ریپلی بزن من بدونم تا کجا قراره ادامه بدم🙃")

    return ""


@run_async
@user_admin
@loggable
def del_message(bot: Bot, update: Update) -> str:
    if update.effective_message.reply_to_message:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        if can_delete(chat, bot.id):
            update.effective_message.reply_to_message.delete()
            update.effective_message.delete()
            return "<b>{}:</b>" \
                   "\n#پاک" \
                   "\n<b>توسط:</b> {}" \
                   "\nپیام پاک شد.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))
    else:
        update.effective_message.reply_text("وجدانن؟")

    return ""


__help__ = """
پیام های اضافه زیاد ، وقت کم؟ برای من مشکلی نیس😇
*فقط ادمین ها* 
- [!پاک] (ریپلی)
[/del] (Reply) 👉 حذف تک P.m
———————————————————--
- [!پاکسازی] (ریپلی) (عدد)
[/purge] (Reply) (INT)👉پاکسازی کلی
———————————————————--
1 : قسمت پاکسازی ریپلی الزامی هست❗️
2 : روی اخرین پیامی که میخوای حذف شه ریپلی بزنی
من از جدید ترین پیام گروه تا وقتی به پیام ریپلی شده برسم
پاکسازی میکنم🙂
3 : اگه عدد هم بدی {ریپلی الزامی} من به تعدادی که 
اشاره کردی پاک میکنم🤓
"""

__mod_name__ = "پاک کن🖱"

DELETE_HANDLER = CommandHandler(["پاک", "del"], del_message, filters=Filters.group)
PURGE_HANDLER = CommandHandler(["پاکسازی", "purge"], purge, filters=Filters.group, pass_args=True)

dispatcher.add_handler(DELETE_HANDLER)
dispatcher.add_handler(PURGE_HANDLER)
