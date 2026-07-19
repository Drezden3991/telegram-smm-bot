import asyncio


async def first_task():
    print("Первая задача началась")

    await asyncio.sleep(2)

    print("Первая задача закончилась")


async def second_task():
    print("Вторая задача началась")

    await asyncio.sleep(1)

    print("Вторая задача закончилась")


async def main():
    await asyncio.gather(
        first_task(),
        second_task()
    )


asyncio.run(main())