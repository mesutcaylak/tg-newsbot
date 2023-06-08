import time, feedparser, sqlite3
from telegram.ext import Application, CommandHandler, ContextTypes, Updater

OUR_CHAT_ID = 1234
CHECK_INTERVAL_IN_MIN = 5

con = sqlite3.connect("haberbotu.db")
cur = con.cursor()


async def kaynak_ekle(update, context):
    for i in range(len(context.args)):
        r = cur.execute("SELECT * from kaynaklar where url='%s'" % (context.args[i])).fetchone()
        if r is None:
            cur.execute("INSERT INTO kaynaklar VALUES('%s')" % (context.args[i]))
            con.commit()

            await update.message.reply_text(context.args[i] + " kaynak olarak eklendi.", disable_web_page_preview=True,
                                            quote=True)

            if job := context.application.job_queue.get_jobs_by_name("haber_cekici")[0]:
                await job.run(application=context.application)
        else:
            await update.message.reply_text(context.args[i] + " zaten eklenmiş.", disable_web_page_preview=True,
                                            quote=True)


async def kaynak_listele(update, context):
    reply = "Takip edilen kaynaklar:\n"

    kaynaklar = cur.execute("SELECT * from kaynaklar").fetchall()

    if len(kaynaklar) == 0:
        return await update.message.reply_text("Kaynak listesi boş.", disable_web_page_preview=True)

    for kaynak in kaynaklar:
        reply += "* " + kaynak[0] + "\n"

    await update.message.reply_text(reply, disable_web_page_preview=True)


async def kaynak_sil(update, context):
    r = cur.execute("SELECT * from kaynaklar where url='%s'" % (context.args[0])).fetchone()
    if r is None:
        return await update.message.reply_text("Böyle bir kaynak yok.", disable_web_page_preview=True, quote=True)

    cur.execute("DELETE FROM kaynaklar where url='%s'" % (context.args[0]))
    con.commit()

    await update.message.reply_text("Kaynak silindi.", disable_web_page_preview=True, quote=True)


async def keyword_ekle(update, context):
    for i in range(len(context.args)):
        r = cur.execute("SELECT * from keywordler where title='%s'" % (context.args[i])).fetchone()
        if r is None:
            cur.execute("INSERT INTO keywordler VALUES('%s')" % (context.args[i]))
            con.commit()

            await update.message.reply_text(context.args[i] + " keyword olarak eklendi.", disable_web_page_preview=True,
                                            quote=True)
        else:
            await update.message.reply_text(context.args[i] + " zaten eklenmiş.", disable_web_page_preview=True,
                                            quote=True)


async def keyword_listele(update, context):
    reply = "Takip edilen keywordler:\n"

    keywordler = cur.execute("SELECT * from keywordler").fetchall()

    if len(keywordler) == 0:
        return await update.message.reply_text("Keyword listesi boş.", disable_web_page_preview=True)

    for keyword in keywordler:
        reply += "* " + keyword[0] + "\n"

    await update.message.reply_text(reply)


async def keyword_sil(update, context):
    r = cur.execute("SELECT * from keywordler where title='%s'" % (context.args[0])).fetchone()
    if r is None:
        return await update.message.reply_text("Böyle bir keyword yok.", quote=True)

    cur.execute("DELETE FROM keywordler where title='%s'" % (context.args[0]))
    con.commit()

    await update.message.reply_text("Keyword silindi.", quote=True)


async def onbellek_temizle(update, context):
    cur.execute("DELETE FROM gonderilenler")
    con.commit()

    await update.message.reply_text("Önbellek temizlendi.", quote=True)


async def haberleri_cek(context: ContextTypes.DEFAULT_TYPE):
    print("Haber cek calisti", time.localtime())

    kaynaklar = cur.execute("SELECT * from kaynaklar").fetchall()
    keywordler = cur.execute("SELECT * from keywordler").fetchall()

    for kaynak in kaynaklar:
        feed = feedparser.parse(kaynak[0])
        for keyword in keywordler:
            hedef_str = str(keyword[0]).replace("+", " ").lower()
            for entry in feed.entries:
                if not (hedef_str in entry.description.lower() or hedef_str in entry.title.lower()):
                    continue

                if not (((time.mktime(time.localtime()) - time.mktime(entry.published_parsed)) / 60) < (60 * 12)):
                    continue

                r = cur.execute("SELECT * from gonderilenler where url='%s'" % (entry.link)).fetchone()
                if r is not None:
                    print(entry.link + " zaten gönderildi.")
                    continue

                cur.execute("INSERT INTO gonderilenler VALUES('%s')" % (entry.link))
                con.commit()

                await context.bot.send_message(
                    chat_id=OUR_CHAT_ID,
                    text="Keyword: " + hedef_str + "\n" + entry.title + "\n\n" + entry.link)


try:
    cur.execute("CREATE TABLE keywordler(title)")
    cur.execute("CREATE TABLE kaynaklar(url)")
    cur.execute("CREATE TABLE gonderilenler(url)")
except sqlite3.OperationalError:
    pass

application = Application.builder().token("*").build()

application.add_handler(CommandHandler("kaynak_ekle", kaynak_ekle))
application.add_handler(CommandHandler("kaynak_listele", kaynak_listele))
application.add_handler(CommandHandler("kaynak_sil", kaynak_sil))

application.add_handler(CommandHandler("keyword_ekle", keyword_ekle))
application.add_handler(CommandHandler("keyword_listele", keyword_listele))
application.add_handler(CommandHandler("keyword_sil", keyword_sil))

application.add_handler(CommandHandler("onbellek_temizle", onbellek_temizle))

job_minute = application.job_queue.run_repeating(haberleri_cek, name="haber_cekici", interval=60 * 10, first=1)
application.run_polling()

