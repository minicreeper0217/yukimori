from aiohttp import web
import aiohttp_jinja2
from datetime import datetime
from zoneinfo import ZoneInfo
from api import APIResponse, APIRouter, rate_limit, turnstile_verify, parse_multipart
from database import DB_PATH
import aiosqlite

routes = web.RouteTableDef()

@routes.get(path="/board")
async def board(request:web.Request):
  async with aiosqlite.connect(DB_PATH) as db:
    cursor = await db.execute("""
      SELECT
        nickname,
        title,
        content,
        created_at
      FROM
        messages
    """)
    rows = await cursor.fetchall()

  messages = []
  for msg in rows:
    messages.append({
      "title": msg[1],
      "content": msg[2],
      "nickname": msg[0],
      "created_at": datetime.fromisoformat(msg[3])
    })

  return aiohttp_jinja2.render_template(
    template_name="board.html",
    request=request,
    context={"messages": messages}
  )

@APIRouter.post(path="/board")
@rate_limit(limit=1, window=300)
async def new_board(request:web.Request):
  data = await parse_multipart(request=request)
  title = data.get("title")
  content = data.get("content")
  nickname = data.get("nickname")
  turnstile_token = data.get("cf-turnstile-response")

  if not all([title, content, nickname, turnstile_token]):
    return APIResponse(
      status=422,
      success=False,
      data={"message": "Unprocessable Entity"}
    )

  turnstile_result = await turnstile_verify(turnstile_token, action="board")
  if not turnstile_result:
    return APIResponse(
      status=401,
      success=False,
      data={"message": "turnstile 驗證失敗"}
    )

  now = datetime.now(tz=ZoneInfo("Asia/Taipei"))
  async with aiosqlite.connect(DB_PATH) as db:
    cursor = await db.execute("""
    INSERT INTO messages (title, content, nickname, created_at)
    VALUES (?, ?, ?, ?)
    """, (title, content, nickname, now.isoformat()))
    message_id = cursor.lastrowid
    await db.commit()

  return APIResponse(
    success=True,
    data={
      "message_id": message_id
    }
  )