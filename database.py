import aiosqlite
import config

DB_PATH = config.dir / "database" / "yukimori.db"

async def init():
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)

	async with aiosqlite.connect(DB_PATH) as db:
		await db.execute("""
			CREATE TABLE IF NOT EXISTS messages (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				nickname TEXT NOT NULL,
				title TEXT NOT NULL,
				content TEXT NOT NULL,
				created_at TEXT NOT NULL
			)
		""")