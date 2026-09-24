RENDER DEPLOY STEPS (Hinglish)
==============================
1. In teeno files (Dockerfile, requirements.txt, insta_worker.py) ko GitHub repo me dalo.
2. render.com -> New -> Background Worker -> repo connect karo.
3. Environment: Docker.
4. Env vars: WORKER_ID=render-1, REDIS_URL=redis://:PASSWORD@HOST:6379/0
   (THREADS khali chhodo = panel dashboard se lega)
5. Plan: Starter ($7/mo) - free par background worker nahi milta.
6. Deploy dabao. Logs me worker start dikhega, panel par heartbeat ayega.

NOTE: Har worker ke liye alag service banao, WORKER_ID alag rakho (render-2, render-3...).
