# 🚀 Deployment Guide: Free Cloud Hosting for CampusConnect ERP

This repository branch (`production`) is pre-configured with **Gunicorn**, **WhiteNoise**, **dynamic environment variables**, and **automated database migrations** so you can deploy CampusConnect on popular free cloud platforms in minutes.

---

## 🏆 Recommended Free Platforms Comparison

| Platform | Free Plan Details | Database Included | Setup Difficulty | Best For |
|---|---|---|---|---|
| **[Render](https://render.com/)** *(Recommended)* | 512 MB RAM, 750 free hours/month, auto SSL | SQLite (local) or Free PostgreSQL | ⭐ Very Easy | **Best overall 1-click deployment** |
| **[Railway](https://railway.app/)** | $5 monthly free trial credit | 1-Click PostgreSQL plugin | ⭐ Very Easy | Fast auto-deployments from Git |
| **[PythonAnywhere](https://www.pythonanywhere.com/)** | Free subdomain (`username.pythonanywhere.com`) | Free MySQL / SQLite with persistent disk | ⭐⭐ Easy | Simple traditional Python hosting |
| **[Koyeb](https://www.koyeb.com/)** | 512 MB RAM free instance | SQLite or external PostgreSQL | ⭐⭐ Moderate | Docker / Git micro-services |

---

## 🛠️ Option 1: Deploying to Render (Recommended – 100% Free)

### Step 1: Push Code to GitHub
Ensure this `production` branch is pushed to your GitHub repository:
```bash
git push -u origin production
```

### Step 2: Create a New Web Service on Render
1. Go to **[dashboard.render.com](https://dashboard.render.com/)** and sign in with your GitHub account.
2. Click **New +** &rarr; Select **Web Service**.
3. Connect your repository: `Abhishek182005/COLLEGE-MANAGEMENT-SYSTEM`.

### Step 3: Configure Settings
Fill in the following fields:

| Field | Value |
|---|---|
| **Name** | `campusconnect-erp` *(or your custom name)* |
| **Region** | Select region closest to your users (e.g., Singapore or Frankfurt) |
| **Branch** | `production` |
| **Runtime** | `Python 3` |
| **Build Command** | `./build.sh` |
| **Start Command** | `gunicorn campusconnect_core.wsgi:application` |
| **Instance Type** | **Free** |

### Step 4: Environment Variables (Under "Advanced")
Add these environment variables:

| Key | Value | Notes |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | Pins exact Python version |
| `DEBUG` | `False` | Disables debug mode for security |
| `SECRET_KEY` | *(Click "Generate" on Render)* | Random 50+ character string |
| `ALLOWED_HOSTS` | `.onrender.com,localhost,127.0.0.1` | Allows Render subdomains |
| `CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` | Prevents CSRF verification errors |

*(Optional)* If you want a persistent PostgreSQL database:
1. Create a free PostgreSQL instance on Render (or [Neon.tech](https://neon.tech/) / [Supabase](https://supabase.com/)).
2. Copy the Connection String and add it as `DATABASE_URL` in your Web Service environment variables.

### Step 5: Deploy!
Click **Create Web Service**.
Render will automatically execute `./build.sh`, run database migrations, populate the demo data, collect static files, and launch your ERP with HTTPS!

Your live URL will look like:
`https://campusconnect-erp.onrender.com`

---

## 🛠️ Option 2: Deploying to Railway

1. Sign in at **[railway.app](https://railway.app/)**.
2. Click **New Project** &rarr; **Deploy from GitHub repo**.
3. Select `Abhishek182005/COLLEGE-MANAGEMENT-SYSTEM` and choose the `production` branch.
4. Railway will automatically detect the `Procfile` and `requirements.txt`.
5. Under **Variables**, add:
   - `DEBUG=False`
   - `SECRET_KEY=your-random-secret-key`
   - `CSRF_TRUSTED_ORIGINS=https://*.railway.app`
6. Under **Settings &rarr; Networking**, click **Generate Domain**.
7. Railway will deploy and provide your live application link!

---

## 🛠️ Option 3: Deploying to PythonAnywhere (Free Tier)

1. Register a free account at **[pythonanywhere.com](https://www.pythonanywhere.com/)**.
2. Open a **Bash Console** and clone the repository:
   ```bash
   git clone -b production https://github.com/Abhishek182005/COLLEGE-MANAGEMENT-SYSTEM.git
   cd COLLEGE-MANAGEMENT-SYSTEM
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 campusconnect-venv
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_data
   python manage.py collectstatic --no-input
   ```
4. Go to the **Web** tab &rarr; **Add a new web app**:
   - Choose **Manual configuration** &rarr; **Python 3.11**.
   - Set **Source code** path: `/home/<username>/COLLEGE-MANAGEMENT-SYSTEM`
   - Set **Virtualenv** path: `/home/<username>/.virtualenvs/campusconnect-venv`
5. Configure the **WSGI configuration file**:
   Replace its content with:
   ```python
   import os
   import sys

   path = '/home/<username>/COLLEGE-MANAGEMENT-SYSTEM'
   if path not in sys.path:
       sys.path.append(path)

   os.environ['DJANGO_SETTINGS_MODULE'] = 'campusconnect_core.settings'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
6. Click **Reload <username>.pythonanywhere.com**!

---

## 🔑 Pre-Seeded Demo Login Credentials

Once deployed, you can immediately log into the live system using:

| Role | Username | Password | Identity |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@123` | Dr. Alok Mukherjee (Full ERP & White-Labeling Control) |
| **Faculty (HOD)** | `prof_sharma` | `Faculty@123` | Dr. Rajesh Sharma (CS501, CS503) |
| **Faculty (Assoc. Prof)** | `prof_verma` | `Faculty@123` | Dr. Anita Verma (CS502, CS504) |
| **Student (Compliant)** | `student_rohit` | `Student@123` | Rohit Kumar (85% Attendance) |
| **Student (Shortage Alert)** | `student_arjun` | `Student@123` | Arjun Mehta (40% Attendance - Shortage Alert) |

---

## 🏷️ Rebranding After Deployment
Once deployed, log into the Admin portal (`admin` / `Admin@123`) and navigate to:
**Reports & System &rarr; College Settings & Branding** (`/accounts/college-settings/`)
Update the college name, seal logo, and address to instantly re-brand your deployed ERP!
