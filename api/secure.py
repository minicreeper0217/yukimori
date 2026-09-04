import config
import aiohttp
from aiohttp import web
import json

async def turnstile_verify(token: str, action: str | None = None) -> bool:
		headers = {
			"Content-Type": "application/json",
		}
		data = {
			"secret": config.cloudflare_turnstile_key,
	 		"response": token
		}
		async with aiohttp.ClientSession() as s:
			async with s.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", headers=headers, data=json.dumps(data)) as r:
				if r.status != 200:
					return False

				payload = await r.json()

		if not payload.get("success") or payload.get("action") != action:
			return False

		return True
