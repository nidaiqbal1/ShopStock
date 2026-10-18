# Publishing ShopStock: GitHub → Vercel → LinkedIn

Replace `YOUR-USERNAME` / `YOUR-LINKEDIN` before you publish. From the project folder:

```
# Windows PowerShell
(Get-Content site\index.html) -replace 'YOUR-USERNAME','your-github-name' -replace 'YOUR-LINKEDIN','your-linkedin-handle' | Set-Content site\index.html
(Get-Content README.md) -replace 'YOUR-USERNAME','your-github-name' | Set-Content README.md
```

## 1. GitHub
1. Create an empty repo named `ShopStock` on github.com (no README, no .gitignore, because the project already has them). Choose **Public**.
2. In the project folder:
   ```
   git init
   git add .
   git status        # check: no .db, .env or secret.key files are listed
   git commit -m "ShopStock v2.3 - Smart Shop & Inventory Management"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/ShopStock.git
   git push -u origin main
   ```
3. On the repo page: add the description *"Smart Shop & Inventory Management — Flask + SQLite POS, khata, inventory, Urdu invoices"* and topics `flask python sqlite pos inventory-management urdu`.
4. Pick a license (Settings → Add file → LICENSE). MIT is common for portfolios. If you plan to sell ShopStock, don't add an open license: see `docs/SELLING_GUIDE.md`.

## 2. Vercel (the project showcase website)
Vercel hosts the static page in `site/`. The Flask app itself is **not** deployed there, because Vercel's servers delete files between requests, so a SQLite shop database would lose data, and a public admin login would expose a shop system to the internet.
1. Go to vercel.com → **Add New → Project** → import the `ShopStock` repo from GitHub.
2. Set **Root Directory** to `site`. Framework Preset: **Other**. Leave build and output settings empty.
3. Click **Deploy**. You get `https://shopstock-xxxx.vercel.app`. Every `git push` redeploys it.
4. Optionally set the website link in the GitHub repo sidebar (About → Website).

## 3. LinkedIn
1. Post the carousel: Start a post → **Add a document** → `docs/linkedin/ShopStock-carousel.pdf`. Paste the caption from `docs/linkedin/LINKEDIN_POST.md`.
2. Put the **GitHub** and **Vercel** links in the first comment.
3. Profile → **Featured** → Add link (the Vercel site) and the repo.
4. Add the project under Profile → Projects, with the Vercel link.

## Before you make the repo public
- The screenshots only show sample data ("Al-Madina General Store"). Don't commit real shop data or backups.
- Never commit `.env` or `instance/`. `.gitignore` already blocks them.
- Change nothing about `admin / admin123`: the app forces a password change at first login.
