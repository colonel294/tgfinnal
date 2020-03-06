from functools import wraps
from typing import Optional

from tg_bot.modules.helper_funcs.misc import is_module_loaded

FILENAME = __name__.rsplit(".", 1)[-1]

if is_module_loaded(FILENAME):
    from telegram import Bot, Update, ParseMode, Message, Chat
    from telegram.error import BadRequest, Unauthorized
    from telegram.ext import CommandHandler, run_async
    from telegram.utils.helpers import escape_markdown

    from tg_bot import dispatcher, LOGGER
    from tg_bot.modules.helper_funcs.chat_status import user_admin
    from tg_bot.modules.sql import log_channel_sql as sql


    def loggable(func):
        @wraps(func)
        def log_action(bot: Bot, update: Update, *args, **kwargs):
            result = func(bot, update, *args, **kwargs)
            chat = update.effective_chat  # type: Optional[Chat]
            message = update.effective_message  # type: Optional[Message]
            if result:
                if chat.type == chat.SUPERGROUP and chat.username:
                    result += "\n<b>لینک:</b> " \
                              "<a href=\"http://telegram.me/{}/{}\">کلیک کن</a>".format(chat.username,
                                                                                           message.message_id)
                log_chat = sql.get_chat_log_channel(chat.id)
                if log_chat:
                    send_log(bot, log_chat, chat.id, result)
            elif result == "":
                pass
            else:
                LOGGER.warning("%s was set as loggable, but had no return statement.", func)

            return result

        return log_action


    def send_log(bot: Bot, log_chat_id: str, orig_chat_id: str, result: str):
        try:
            bot.send_message(log_chat_id, result, parse_mode=ParseMode.HTML)
        except BadRequest as excp:
            if excp.message == "Chat not found":
                bot.send_message(orig_chat_id, "ارتباطم قطع شد . خواهشا دوباره وصلم کن!")
                sql.stop_chat_logging(orig_chat_id)
            else:
                LOGGER.warning(excp.message)
                LOGGER.warning(result)
                LOGGER.exception("Could not parse")

                bot.send_message(log_chat_id, result + "\n\nپاکسازی به علت یه خطای غیر منتظره قطع شذ.")


    @run_async
    @user_admin
    def logging(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]

        log_channel = sql.get_chat_log_channel(chat.id)
        if log_channel:
            log_channel_info = bot.get_chat(log_channel)
            message.reply_text(
                "هر اتفاقی اینجا بیوفته من میفرستم به چنل: {} (`{}`)".format(escape_markdown(log_channel_info.title),
                                                                         log_channel),
                parse_mode=ParseMode.MARKDOWN)

        else:
            message.reply_text("هنو آنتن من ست نشده!😕")


    @run_async
    @user_admin
    def setlog(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]
        if chat.type == chat.CHANNEL:
            message.reply_text("خب حالا پیام !خبر یا /setlog رو به گپ فور کن")

        elif message.forward_from_chat:
            sql.set_chat_log_channel(chat.id, message.forward_from_chat.id)
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("Error deleting message in log channel. Should work anyway though.")

            try:
                bot.send_message(message.forward_from_chat.id,
                                 "این کانال تنطیم شده برای اخبار گپ {}.".format(
                                     chat.title or chat.first_name))
            except Unauthorized as excp:
                if excp.message == "Forbidden: bot is not a member of the channel chat":
                    bot.send_message(chat.id, "متصل شدیم😎")
                else:
                    LOGGER.exception("ERROR in setting the log channel.")

            bot.send_message(chat.id, "متصل شدیم😎")

        else:
            message.reply_text("مراحل لینک کردن من و کانال:\n"
                               " - منو ادد کن تو چنلت\n"
                               " - دستور !خبر یا /setlog رو داخل چنل بفرس\n"
                               " - پیام !خبر یا /setlog رو فوروارد کن تو گپت\n")


    @run_async
    @user_admin
    def unsetlog(bot: Bot, update: Update):
        message = update.effective_message  # type: Optional[Message]
        chat = update.effective_chat  # type: Optional[Chat]

        log_channel = sql.stop_chat_logging(chat.id)
        if log_channel:
            bot.send_message(log_channel, "کانال با گپ {} لینک شد!".format(chat.title))
            message.reply_text("اتصال ما قطع شد!!")

        else:
            message.reply_text("هنو آنتن من ست نشده!😕")


    def __stats__():
        return "{} کانال خبر تنظیم شد.".format(sql.num_logchannels())


    def __migrate__(old_chat_id, new_chat_id):
        sql.migrate_chat(old_chat_id, new_chat_id)


    def __chat_settings__(chat_id, user_id):
        log_channel = sql.get_chat_log_channel(chat_id)
        if log_channel:
            log_channel_info = dispatcher.bot.get_chat(log_channel)
            return "این گپ تمامی اخبارش رو میفرسته به: {} (`{}`) ".format(escape_markdown(log_channel_info.title),
                                                                            log_channel)
        return "کانال اخباری هنوز برای اینجا تنظیم نشده."


    __help__ = """
	اگه بخوای من میتونم تمامی کارهایی که انجام میدم رو 
داخل یه کانال لیست کنم 👩🏻‍🏭
مثل یه گزارش نامه آنی

*فقط ادمین ها*
- [!گزارش]
[/log] 👉اطلاع از وضعیت آنتن
———————————————————--
مراحل ست کردن آنتن : 🙄
1.ادد کردن ربات در کانال (به عنوان ادمین)
2.ارسال دستور [!خبر] یا [/setlog] داخل کانال
3.فوروارد دستور از کانال به گپ
———————————————————--
- [!خبر0]
[/unsetlog] 👉 قطع اتصال آنتن
"""

    __mod_name__ = "آنتن📡"

    LOG_HANDLER = CommandHandler(["گزارش", "log"], logging)
    SET_LOG_HANDLER = CommandHandler(["خبر", "setlog"], setlog)
    UNSET_LOG_HANDLER = CommandHandler(["خبر0", "unsetlog"], unsetlog)

    dispatcher.add_handler(LOG_HANDLER)
    dispatcher.add_handler(SET_LOG_HANDLER)
    dispatcher.add_handler(UNSET_LOG_HANDLER)

else:
    # run anyway if module not loaded
    def loggable(func):
        return func
