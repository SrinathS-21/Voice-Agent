import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Ensure CONVEX_DEPLOY_KEY is present
if "CONVEX_DEPLOY_KEY" not in os.environ:
    print("❌ CONVEX_DEPLOY_KEY not found in .env")
    exit(1)

print(f"Deploying to Convex: {os.environ.get('CONVEX_URL', 'unknown')}")

# Run deploy command
try:
    # On Windows shell=True might be needed for npx
    subprocess.run(["npx", "convex", "deploy"], shell=True, check=True, env=os.environ, cwd=str(env_path.parent))
    print("✅ Deployment successful!")
except subprocess.CalledProcessError as e:
    print(f"❌ Deployment failed with exit code {e.returncode}")
    exit(e.returncode)
