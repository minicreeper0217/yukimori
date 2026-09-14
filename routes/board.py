from aiohttp import web
import aiohttp_jinja2
from datetime import datetime
from zoneinfo import ZoneInfo
from api import APIResponse, APIRouter, rate_limit, turnstile_verify, parse_multipart
from database import DB_PATH
import aiosqlite

routes = web.RouteTableDef()

MESSAGES_PER_PAGE = 15

@routes.get(path="/board")
async def board(request: web.Request):
	try:
		page = int(request.query.get("page", "1"))
	except ValueError:
		page = 1

	page = max(page, 1)

	offset = (page - 1) * MESSAGES_PER_PAGE

	async with aiosqlite.connect(DB_PATH) as db:
		cursor = await db.execute("""
			SELECT COUNT(*)
			FROM messages
		""")
		total_count = (await cursor.fetchone())[0]

		total_pages = max((total_count + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE, 1)
		if page > total_pages:
			page = total_pages
			offset = (page - 1) * MESSAGES_PER_PAGE

		cursor = await db.execute("""
			SELECT
				nickname,
				title,
				content,
				created_at
			FROM
				messages
			ORDER BY
				id DESC
			LIMIT ?
			OFFSET ?
		""", (MESSAGES_PER_PAGE, offset))

		rows = await cursor.fetchall()
		pagination = get_pagination(page, total_pages)

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
		context={
			"messages": messages,
			"page": page,
			"total_pages": total_pages,
			"pagination": pagination,
		}
	)

def get_pagination(page: int, total_pages: int) -> list[int | None]:
	if total_pages <= 7:
		return list(range(1, total_pages + 1))

	pages = {1, total_pages}

	for number in range(page - 2, page + 3):
		if 1 <= number <= total_pages:
			pages.add(number)

	result = []
	previous = None

	for number in sorted(pages):
		if previous is not None and number - previous > 1:
				result.append(None)

		result.append(number)
		previous = number

	return result

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

	title = title.strip()
	content = content.strip()
	nickname = nickname.strip()

	# 清除空白之後再檢查一次
	if not all([title, content, nickname]):
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
		data={"message_id": message_id}
	)