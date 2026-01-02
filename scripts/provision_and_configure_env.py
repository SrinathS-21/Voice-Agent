"""
Provision a tenant using platform Twilio and update .env with purchased phone number.

Usage:
  python scripts/provision_and_configure_env.py --slug demo --name "Demo Tenant" [--country US]

This will:
  - call TwilioProvisioner.provision_for_tenant
  - update the repository `.env` to set `TWILIO_PHONE_NUMBER` to the purchased number
  - print the provision result

Note: This performs billable Twilio operations.
"""
import argparse
import asyncio
import os
from pathlib import Path

from app.services.twilio_service import TwilioProvisioner
from app.repositories.tenant_repository import get_tenant_repository

tenant_repo = get_tenant_repository()


async def provision_and_write_env(slug: str, name: str, country: str = "US", voice_url: str = None):
    prov = TwilioProvisioner()

    # If tenant exists, reuse it; otherwise create tenant and provision everything
    existing = await tenant_repo.get_by_slug(slug)
    if existing:
        print(f"Tenant with slug '{slug}' already exists (id={existing.id}), continuing Twilio provisioning")
        # create twiml app
        app_sid = await prov.create_twiml_app(friendly_name=f"{slug}-twiml-app", voice_url=voice_url)
        # buy number
        phone_number, number_sid = await prov.buy_number(country=country)
        # attach
        await prov.attach_number_to_app(number_sid=number_sid, app_sid=app_sid)
        # persist
        phone_config = await tenant_repo.add_phone_number(
            tenant_id=existing.id,
            phone_number=phone_number,
            job_type="restaurant",
            config_json={"twiml_app_sid": app_sid}
        )

        res = {
            "tenant": {"id": existing.id, "slug": existing.slug, "name": existing.name},
            "phone": {"phone_number": phone_number, "number_sid": number_sid, "twiml_app_sid": app_sid, "phone_config_id": phone_config.id}
        }
        phone_number = phone_number
    else:
        res = await prov.provision_for_tenant(slug=slug, client_name=name, job_type="restaurant", voice_url=voice_url, country=country)
        phone = res.get("phone", {})
        phone_number = phone.get("phone_number")

    if not phone_number:
        print("Provisioning completed but no phone number found in result:", res)
        return res

    # Update .env file in repo root
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root.joinpath('.env')
    if not env_path.exists():
        print(f".env not found at {env_path}, creating new one")
        env_text = ''
    else:
        env_text = env_path.read_text(encoding='utf-8')

    lines = env_text.splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('TWILIO_PHONE_NUMBER='):
            new_lines.append(f"TWILIO_PHONE_NUMBER={phone_number}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"TWILIO_PHONE_NUMBER={phone_number}")

    env_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f"Wrote TWILIO_PHONE_NUMBER={phone_number} to {env_path}")
    print("Provision result:", res)
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--country', default='US')
    parser.add_argument('--voice-url', default=None)
    args = parser.parse_args()

    asyncio.run(provision_and_write_env(args.slug, args.name, country=args.country, voice_url=args.voice_url))


if __name__ == '__main__':
    main()
