from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import time
from collections import deque
import logging

from aiohttp import web


@dataclass
class APIResponse:
  success: bool
  data: dict | list
  status: int = 200

  def to_dict(self) -> dict:
    return {
      "success": self.success,
      "data": self.data
    }


# Rate Limit -------------------------------------------------------------------

@dataclass
class RateLimit:
  limit: int
  window: int

def rate_limit(limit: int, window: int):
  def decorator(handler):
    # 只保存 metadata，不改變 handler
    handler.__rate_limit__ = RateLimit(
      limit=limit,
      window=window
    )

    return handler

  return decorator


# Route ------------------------------------------------------------------------

@dataclass
class Route:
  method: str
  path: str
  handler: Callable[..., Awaitable[Any]]
  rate_limit: RateLimit | None = None

  def __post_init__(self):
    self.method = self.method.upper()

    self.parts = [
      part
      for part in self.path.strip("/").split("/")
      if part
    ]

  def match(
    self,
    method: str,
    path: str
  ) -> dict | None:

    if self.method != method.upper():
      return None

    parts = [
      part
      for part in path.strip("/").split("/")
      if part
    ]

    if len(parts) != len(self.parts):
      return None

    params = {}

    for pattern, value in zip(self.parts, parts):

      # {user_id}
      if (
        pattern.startswith("{")
        and pattern.endswith("}")
      ):
        name = pattern[1:-1]

        if not name:
          return None

        params[name] = value

      # 普通 path
      elif pattern != value:
        return None

    return params


# Router -----------------------------------------------------------------------

class APIRouter:
  routes: list[Route] = []

  @classmethod
  def route(
    cls,
    method: str,
    path: str
  ):
    def decorator(handler):
      route = Route(
        method=method,
        path=path,
        handler=handler,
        rate_limit=getattr(
          handler,
          "__rate_limit__",
          None
        )
      )

      cls.routes.append(route)

      return handler

    return decorator

  @classmethod
  def get(cls, path: str):
    return cls.route("GET", path)

  @classmethod
  def post(cls, path: str):
    return cls.route("POST", path)

  @classmethod
  def patch(cls, path: str):
    return cls.route("PATCH", path)

  @classmethod
  def delete(cls, path: str):
    return cls.route("DELETE", path)

  @classmethod
  def match(
    cls,
    method: str,
    path: str
  ) -> tuple[Route, dict] | None:

    for route in cls.routes:
      params = route.match(
        method,
        path
      )

      if params is not None:
        return route, params

    return None


# Rate Limiter -----------------------------------------------------------------

class RateLimiter:
  def __init__(self):
    self.requests: dict[str, deque[float]] = {}

  async def allow(
    self,
    request: web.Request,
    rate_limit
  ) -> bool:

    key = self.get_key(request)
    now = time.monotonic()

    requests = self.requests.setdefault(
      key,
      deque()
    )

    # 移除時間窗外的 request
    while requests and now - requests[0] >= rate_limit.window:
      requests.popleft()

    # 已經達到限制
    if len(requests) >= rate_limit.limit:
      return False

    requests.append(now)

    return True

  def get_key(
    self,
    request: web.Request
  ) -> str:

    return f"{request.headers['X-Real-IP']}:{request.match_info['route']}"

rate_limiter = RateLimiter()


# API Middleware ---------------------------------------------------------------

async def api_middle(
  request: web.Request
) -> web.Response:

  result = APIRouter.match(
    method=request.method,
    path=request.match_info["route"]
  )

  if result is None:
    return web.json_response(
      APIResponse(
        success=False,
        data={
          "message": "Not Found"
        }
      ).to_dict(),
      status=404
    )

  route, params = result

  # Rate Limit -----------------------------------------------------------------

  if route.rate_limit is not None:
    allowed = await rate_limiter.allow(
      request,
      route.rate_limit
    )

    if not allowed:
      return web.json_response(
        APIResponse(
          success=False,
          data={
            "message": "Too Many Requests"
          }
        ).to_dict(),
        status=429
      )

  # API Handler ----------------------------------------------------------------

  try:
    response = await route.handler(
      request,
      **params
    )

    if not isinstance(response, APIResponse):
      raise TypeError(
        f"API Handler must return APIResponse, Not {type(response).__name__}."
      )

    return web.json_response(data=response.to_dict(), status=response.status)

  except Exception:
    logging.exception("API Handler Error!")
    return web.json_response(
      APIResponse(
        success=False,
        data={
          "message": "Internal Server Error"
        }
      ).to_dict(),
      status=500
    )


# aiohttp registration --------------------------------------------------------

def register(app: web.Application):
  app.router.add_route(
    "GET",
    "/api/{route:.*}",
    api_middle
  )

  app.router.add_route(
    "POST",
    "/api/{route:.*}",
    api_middle
  )

  app.router.add_route(
    "PATCH",
    "/api/{route:.*}",
    api_middle
  )

  app.router.add_route(
    "DELETE",
    "/api/{route:.*}",
    api_middle
  )


# etc -------------------------------------------------------------------------

async def parse_multipart(
  request: web.Request
) -> dict:

  if request.content_type != "multipart/form-data":
    return {}

  reader = await request.multipart()
  data = {}

  async for part in reader:
    if part.filename:
      data[part.name] = {
        "filename": part.filename,
        "content_type": part.headers.get(
          "Content-Type"
        ),
        "data": await part.read()
      }
    else:
      data[part.name] = await part.text()

  return data