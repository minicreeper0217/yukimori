from aiohttp import web
import aiohttp
from aiohttp import web_exceptions
import json
import aiohttp_jinja2
import jinja2
import logging
import logging.handlers
import config
import asyncio
from routes import routes

main_routes = web.RouteTableDef()

@main_routes.get(path="/homepage")
async def homepage(request:web.Request):
	return aiohttp_jinja2.render_template(
		template_name="homepage.html",
		request=request,
		context=None
	)

@web.middleware
async def middle(request:web.Request, handler):
	if not request.headers.get('X-Real-IP') or not request.headers.get('User-Agent'):
		return web.Response(status=400,text="")
	if all(request.method != x for x in ["GET", "POST"]):
		return web.Response(status=405,text="")
	try:
		if handler.__name__ == "_handle":
			return web.Response(status=404,text="")
		response = await handler(request)
		return response
	except web_exceptions.HTTPNotFound:
		return web.Response(status=404,text="")
	except:
		ex = {"Code": 500, "Message": "Internal_Server_Error"}
		logging.exception(f"An error occurred while handling request!")
		return web.Response(status=500,text=json.dumps(ex), content_type="application/json")

async def run():
	app = web.Application(client_max_size=8*(1024**2))
	app.add_routes(main_routes)
	app.add_routes(*routes)
	aiohttp_jinja2.setup(app=app,loader=jinja2.FileSystemLoader("html"))
	handler = logging.handlers.RotatingFileHandler(filename=config.dir / 'logs' / 'webapplog.txt',maxBytes=1048576,backupCount=2,encoding="UTF-8")
	handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
	logger = logging.getLogger("webapp")
	logger.addHandler(handler)
	logger.setLevel(logging.INFO)
	runner = web.AppRunner(app,access_log_format='%{X-Real-IP}i "%{X-Method}i" %s %{Content-Length}i "%{User-Agent}i" (%D)', access_log = logger)
	await runner.setup()
	site = web.TCPSite(runner, host='localhost',port=3050)
	await site.start()

	try:
		await asyncio.Event().wait()

	finally:
		await runner.cleanup()

if __name__ == "__main__":
	try:
		asyncio.run(run())
	except KeyboardInterrupt:
		pass