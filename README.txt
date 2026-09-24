RENDER + GITHUB ACTIONS SETUP (Hinglish)
========================================

GITHUB ACTIONS (free, auto-restart har 5h):
1. Is zip ko unzip karke SARI files GitHub repo me dalo
   (folder structure aisi honi chahiye: .github/workflows/worker.yml)
2. Repo -> Settings -> Secrets and variables -> Actions -> 2 secrets:
   REDIS_URL = redis://:PASSWORD@HOST:6379/0
   WORKER_ID = github-1
3. Actions tab -> Insta Worker -> Run workflow
   (uske baad har 5 ghante auto-restart; 6h limit se pehle)
4. Panel par github-1 heartbeat ayega.

RENDER (paid $7/mo, 24/7 no restart):
1. Upar wali files wala repo Render se connect karo.
2. New -> Background Worker -> Docker environment.
3. Start Command: python insta_worker.py --worker-id $WORKER_ID
4. Env vars: WORKER_ID=render-1, REDIS_URL=redis://:PASSWORD@HOST:6379/0
5. Plan: Starter. Deploy dabao.

THREADS: dono me dashboard (Fleet threads) se ayenge.
NOTE: Har worker ka WORKER_ID alag rakho (github-2, render-2...).
