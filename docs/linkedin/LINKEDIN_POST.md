# LinkedIn post (copy & paste) — attach `ShopStock-carousel.pdf` as a document, or use `ShopStock-cover.png` as the image

---

🏪 I built ShopStock — a complete shop & inventory management system for small retail shops in Pakistan.

Many general stores still run on paper registers: lost khata pages, no clear view of real profit, stock-outs noticed too late. I wanted to build something that fits how shopkeepers really work.

What it does:
✅ POS with barcode search — Cash, Bank, Easypaisa, JazzCash & Credit/Udhaar
✅ Khata (udhaar) with statements and WhatsApp payment reminders
✅ Inventory, suppliers, purchases & expenses
✅ Profit, receivables and low-stock insights on a live dashboard
✅ PDF invoices & reports (English + Urdu), Excel export, thermal receipts
✅ Returns/void, daily automatic backups, Owner/Cashier roles
✅ Read-only AI assistant that answers from real shop data only

Under the hood: Python · Flask · SQLAlchemy · SQLite · ReportLab · Bootstrap 5 · Chart.js — with 189 automated end-to-end tests and Windows packaging scripts.

The biggest lessons: money logic must be derived, never typed (khata balances are always calculated from records), and "works on my machine" isn't enough — I tested the UI in a real browser and fixed layout and chart bugs I'd never have caught by reading code.

Source code and screenshots: link in the first comment 👇
I'd love your feedback — especially from anyone who has worked with small retail businesses. 👇

#Python #Flask #FullStack #WebDevelopment #SQLite #Pakistan #SoftwareEngineering #Portfolio #FYP #OpenSource

---
Tips: post on a weekday morning, add the GitHub link in the first comment (LinkedIn reduces reach for links in the post body), and reply to every comment in the first hour.

## Publishing (GitHub, Vercel, LinkedIn)
See `docs/PUBLISHING.md` for the exact commands and Vercel settings (Root Directory = `site`).

## GitHub upload checklist
1. Create a new repo "ShopStock" → upload the project folder (do NOT upload `instance/`, `backups/` or `.env`; `.gitignore` already excludes them).
2. Set the repo description: "Smart Shop & Inventory Management — Flask + SQLite POS, khata, inventory, Urdu invoices".
3. Add topics: flask, python, sqlite, pos, inventory-management, urdu.
4. Pin the repo on your GitHub and add it under LinkedIn → Featured.
