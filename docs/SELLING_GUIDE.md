# Selling ShopStock — practical checklist (for the seller)

**Before the first customer**
- Build on Windows with `build_windows.bat`, then `installer.iss` (Inno Setup). Test the installer on a clean PC (Windows 10/11).
- Decide your price model (one-time licence + yearly support is common) and put your name/phone in the Settings defaults of the copy you hand over.
- Fill in `LICENSE-TEMPLATE.txt` with your details and have a local lawyer review it. It limits liability for data loss and states what support includes.

**Installing at a shop (30 minutes)**
1. Run `ShopStock-Setup.exe`. 2. Log in, change the password, fill Settings. 3. Create the owner's own user and a cashier user. 4. Enter categories/products (or import by typing; Excel *import* is not included). 5. Set *Extra backup folder* to a USB drive or OneDrive folder. 6. Print a test receipt/invoice. 7. Give them `docs/USER_GUIDE.md`.

**Support habits**
- Tell every customer: backups matter. Ask them to copy a backup to USB weekly.
- Keep a note of each shop's version. Updates: install the new setup over the old one — data in `%LOCALAPPDATA%\ShopStock` is kept and the database upgrades itself.
- Remote help: ask for the file `shopstock.db` backup (Backup & Restore → Download) if you need to investigate a problem.

**Be clear with customers about limits**: no FBR integration, English-only report PDFs (invoices/statements can be Urdu), single shop/branch, no cloud sync.
