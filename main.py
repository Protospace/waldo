from twilio.twiml.messaging_response import MessagingResponse
from telethon import TelegramClient, events
from aiohttp import web
import asyncio

import settings

bot = TelegramClient('bot', settings.API_ID, settings.API_HASH).start(bot_token=settings.API_TOKEN)
app = web.Application()

@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.reply('Howdy, how are you doing?')

@bot.on(events.NewMessage)
async def echo_all(event):
    await event.reply(event.text)

async def index(request):
    return web.Response(text='Hello, world')

async def sms(request):
    data = await request.post()
    print(data)

    resp = MessagingResponse()
    resp.message('reply')
    return web.Response(body=str(resp), content_type='application/xml')

async def main():
    app.router.add_get('/', index)
    app.router.add_post('/sms', sms)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8083)
    await site.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())

    bot.run_until_disconnected()
