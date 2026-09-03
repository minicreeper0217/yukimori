from aiohttp import web
import aiohttp_jinja2
from datetime import datetime

routes = web.RouteTableDef()

@routes.get(path="/board")
async def board(request:web.Request):
  return aiohttp_jinja2.render_template(
    template_name="board.html",
    request=request,
    context={"messages":[]}
  )