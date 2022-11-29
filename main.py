import asyncio

from src.test import FakeApplication, test_decorators


async def run_test_as_main():
	app = FakeApplication()
	await test_decorators(app)


if __name__ == '__main__':
	asyncio.run(run_test_as_main())
