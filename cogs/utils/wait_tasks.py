import asyncio


async def wait_tasks(tasks, cond):
    # Wait for a list of asyncio tasks to complete.
    # cond=True -> ANY, cond=False -> ALL
    if not tasks:
        return True

    while tasks:
        done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            if await d is cond:
                for t in tasks:
                    t.cancel()
                return cond
    return not cond


async def wait_tasks_any(tasks):
    return await wait_tasks(tasks, True)


async def wait_tasks_all(tasks):
    return await wait_tasks(tasks, False)
