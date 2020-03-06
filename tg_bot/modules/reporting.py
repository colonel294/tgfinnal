import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User, ParseMode
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, RegexHandler, run_async, Filters
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_not_admin, user_admin
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import reporting_sql as sql

REPORT_GROUP = 5


@run_async
@user_admin
def report_setting(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if chat.type == chat.PRIVATE:
        if len(args) >= 1:
            if args[0] in ("روشن", "on"):
                sql.set_user_setting(chat.id, True)
                msg.reply_text("حالت خبرچین فعال شد! اگه کسی درخواست بده سریعا بهتون اطلاع میدم.")

            elif args[0] in ("خاموش", "off"):
                sql.set_user_setting(chat.id, False)
                msg.reply_text("حالت خبرچین غیرفعال شد! کسی بمیره هم بهت اطلاع نمیدم😄")
        else:
            msg.reply_text("حالت خبرچین شما : `{}`".format(sql.user_should_report(chat.id)),
                           parse_mode=ParseMode.MARKDOWN)

    else:
        if len(args) >= 1:
            if args[0] in ("روشن", "on"):
                sql.set_chat_setting(chat.id, True)
                msg.reply_text("خبرچین گپ فعال شد ، اگه کسی از دستور ریپورت یا /report روی کسی"
                               "ریپلی کنه من سریعا به ادمینها اطلاع میدم.")

            elif args[0] in ("غیرفعال", "off"):
                sql.set_chat_setting(chat.id, False)
                msg.reply_text("حالت خبرچین غیرفعال شد . اینجا همدیگه هم بکشن ، من صدام درنمیاد☹️.")
        else:
            msg.reply_text("حالت خبرچین این گپ: `{}`".format(sql.chat_should_report(chat.id)),
                           parse_mode=ParseMode.MARKDOWN)


@run_async
@user_not_admin
@loggable
def report(bot: Bot, update: Update) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if chat and message.reply_to_message and sql.chat_should_report(chat.id):
        reported_user = message.reply_to_message.from_user  # type: Optional[User]
        chat_name = chat.title or chat.first or chat.username
        admin_list = chat.get_administrators()

        if chat.username and chat.type == Chat.SUPERGROUP:
            msg = "<b>{}:</b>" \
                  "\n<b>کاربر گزارش شده:</b> {} (<code>{}</code>)" \
                  "\n<b>توسط:</b> {} (<code>{}</code>) مشخص شد!".format(html.escape(chat.title),
                                                                      mention_html(
                                                                          reported_user.id,
                                                                          reported_user.first_name),
                                                                      reported_user.id,
                                                                      mention_html(user.id,
                                                                                   user.first_name),
                                                                      user.id)
            link = "\n<b>لینک:</b> " \
                   "<a href=\"http://telegram.me/{}/{}\">کلیک کن</a>".format(chat.username, message.message_id)

            should_forward = False

        else:
            msg = "کاربر {} درگپ \"{}\"درخواست ادمین کرده . خواهشا زود بیا!".format(mention_html(user.id, user.first_name),
                                                               html.escape(chat_name))
            link = ""
            should_forward = True

        for admin in admin_list:
            if admin.user.is_bot:  # can't message bots
                continue

            if sql.user_should_report(admin.user.id):
                try:
                    bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML)

                    if should_forward:
                        message.reply_to_message.forward(admin.user.id)

                        if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                            message.forward(admin.user.id)

                except Unauthorized:
                    pass
                except BadRequest as excp:  # TODO: cleanup exceptions
                    LOGGER.exception("Exception while reporting user")
        return msg

    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "حالت خبرچین این گپ *{}* است ، کاربرا میتونن با دستور ریپورت مشکل رو گزارش بدن!".format(
        sql.chat_should_report(chat_id))


def __user_settings__(user_id):
    return "وضعیت اطلاع گزارش شما *{}* هست! ".format(
        sql.user_should_report(user_id))


__mod_name__ = "خبرچین"

__help__ = """
خبرچینی کار بدیه میدونم😶 ولی گاهی لازمه❗️
- [!ریپورت] [ریپورت] (ریپلی) (دلیل اختیاری)
[/report] [@admin] (Reply) (Reason)👉
خبرچین
———————————————————--
- [!خبرچین] (روشن یا خاموش) 
[/reporting] (on OR off) 👉 کلیدخبرچین
———————————————————--
* 1 : اگه به موردی غیرمجاز برخورد کردید میتونید با ریپلی زدن و یکی از 4 دستور تعریف شده ، به ادمین ها گزارشش کنید
   2 : حالت خبرچین پیشفرض خاموش هست!
"""

REPORT_HANDLER = CommandHandler(["ریپورت", "report"], report, filters=Filters.group)
SETTING_HANDLER = CommandHandler(["خبرچین", "reporting"], report_setting, pass_args=True)
ADMIN_REPORT_HANDLER = RegexHandler(["(?i)ریپورت(s)?", "(?i)@admin(s)?"], report)

dispatcher.add_handler(REPORT_HANDLER, REPORT_GROUP)
dispatcher.add_handler(ADMIN_REPORT_HANDLER, REPORT_GROUP)
dispatcher.add_handler(SETTING_HANDLER)
