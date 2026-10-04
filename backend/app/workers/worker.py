from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url)
    worker = Worker([Queue("tripwise", connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
