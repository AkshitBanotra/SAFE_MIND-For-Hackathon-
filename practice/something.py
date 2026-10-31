#!/usr/bin/env python3

import asyncio

async def fetch_data():
    await asyncio.sleep(1)
    print("data")

#result = fetch_data()
print(asyncio.run(fetch_data))
