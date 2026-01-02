import asyncio
import argparse

from app.repositories.tenant_repository import get_tenant_repository


async def main(slug: str, name: str):
    repo = get_tenant_repository()
    tenant = await repo.create_tenant(name=name, slug=slug)
    print("Created tenant:", tenant.id, tenant.slug, tenant.name)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--name", required=True)
    args = p.parse_args()
    asyncio.run(main(args.slug, args.name))
