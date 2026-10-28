# Nazrul Sishu Siksha Niketan — Online Admission Portal

Responsive English-language admission portal based on the school's paper form. Includes application submission, SQLite storage, automatically generated application numbers, admin login, application search/status updates, private document downloads and CSV export.

## Payment status
**Online payment is intentionally disabled for now.** The admission fee defaults to ₹0 and applications show payment as “Not Required”. No card/UPI payment is taken and no payment is falsely marked successful. Payment can be added later after the school chooses and verifies a payment gateway account.

## Test locally (Windows)
1. Install Python 3.10+.
2. Extract this ZIP and open a terminal in the `nazrul_admission_portal` folder.
3. Run `py -m venv .venv`
4. Run `.venv\\Scripts\\activate`
5. Run `pip install -r requirements.txt`
6. Set environment variables before launch:
   - PowerShell: `$env:ADMIN_USER="schooladmin"`
   - PowerShell: `$env:ADMIN_PASSWORD="Use-a-long-unique-password"`
   - PowerShell: `$env:SECRET_KEY="Use-a-long-random-secret"`
7. Run `python app.py` and open `http://127.0.0.1:5000`.
8. Admin login: `http://127.0.0.1:5000/admin/login`.

## Deployment to Render
1. Create a Git repository from this project and push it to your own GitHub account.
2. In Render, choose **New > Blueprint** and connect that repository; Render will read `render.yaml`.
3. Enter a strong unique `ADMIN_PASSWORD` when prompted. Keep it private.
4. Review the service and persistent disk cost/plan before confirming. The included blueprint uses a persistent disk so SQLite data and uploaded files survive redeploys; hosting may not be free.
5. After deployment, test an application and admin login. Use the generated HTTPS URL to share the form.

This project is prepared for deployment but is **not published yet**. Creating a public URL requires the school owner to sign in to a hosting provider and approve its hosting/billing settings. Do not upload real student data until security, access controls, backup and privacy requirements have been reviewed.

## Before public launch
- Confirm all 17 paper-form sections, required fields, class list, school contact details, photo/document requirements and declarations with the school.
- Keep Aadhaar optional unless collection is necessary and legally justified.
- Set a strong admin password and secret key; never commit secrets to GitHub.
- Use HTTPS, persistent storage and secure backups. Restrict access to the admin panel and uploaded files.
- Add CSRF protection, rate limiting, audit logs and a retention/deletion policy before collecting real student information.
- Payment is not enabled. If added later, implement provider-side order creation, server-side signature verification and webhook reconciliation before taking fees.
