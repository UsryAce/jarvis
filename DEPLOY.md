# Free Deployment Options for JARVIS

## Option 1: Render.com (Recommended - Free Tier)
1. Push to GitHub
2. Connect to Render.com
3. Create Web Service
4. Auto-deploys on push

## Option 2: Fly.io (Free Tier)
```bash
fly launch --no-deploy
fly deploy
```

## Option 3: Google Cloud Run (Free Tier)
```bash
gcloud run deploy jarvis --source . --platform managed --region us-central1 --allow-unauthenticated
```

## Option 4: Local Docker (Always Free)
```bash
docker-compose up -d
```

## Option 5: Self-hosted VPS (DigitalOcean/Linode/Vultr ~$4-5/mo)
```bash
# On VPS
git clone <your-repo>
cd jarvis
docker-compose up -d
```

---

## Quick Start (Docker Compose)

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

## Environment Variables
Copy `.env.example` to `.env` and add your NVIDIA_API_KEY

## Free Hosting Comparison

| Platform | Free Tier | Docker Support | Custom Domain | Sleep on Inactive |
|----------|-----------|----------------|---------------|-------------------|
| Render.com | ✅ 750 hrs/mo | ✅ | ✅ | Yes (15 min) |
| Fly.io | ✅ 3 shared CPUs | ✅ | ✅ | No |
| Cloud Run | ✅ 2M requests/mo | ✅ | ✅ | No |
| Railway | ❌ Trial only | ✅ | ✅ | Yes |
| Heroku | ❌ No free tier | ✅ | ✅ | Yes |

## Recommendation: Fly.io or Cloud Run
- No sleep/wake cycle
- Generous free tiers
- Native Docker support
- Global edge deployment