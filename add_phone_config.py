import asyncio
from app.models.database import async_session_maker, PhoneNumberConfig

async def add_config():
    async with async_session_maker() as session:
        config = PhoneNumberConfig(
            phone_number='+13047185875',
            config_data={"greeting": "Hello, this is your AI agent!"}
        )
        session.add(config)
        await session.commit()
        print("Config added for +13047185875")

if __name__ == "__main__":
    asyncio.run(add_config())
