# Running the app on another computer

A step-by-step guide for starting the Inventory & POS app on a computer that has never run it,
for example a school lab computer, straight from this GitHub repository. Written for Windows;
macOS and Linux differences are at the end.

**Time needed:** about 10 minutes, most of it downloading.
**Tested:** a fresh copy of `main` (v0.20.5) on 2026-10-13: install, demo data, log-in, New Sale.

---

## What you need first

| Thing | Why | How to check |
|---|---|---|
| **Python 3.11 or newer** (3.11 and 3.13 are tested) | The app is written in Python | Open *Command Prompt* and type `python --version` |
| **Internet**, for step 3 only | To download the packages the app uses (about 3 MB) | No internet? See [Plan B](#plan-b-no-internet-on-that-computer) |
| **Git** (optional) | To download the code with one command | `git --version`. No Git? Use the ZIP download in step 1 |

**Words used below**

- **Terminal**: the window where you type commands. On Windows this is *Command Prompt* (cmd) or
  *PowerShell*. Every command in this guide works in both.
- **Repository (repo)**: the project's folder on GitHub, with all its history.
- **Virtual environment (venv)**: a private folder of packages just for this project, so it does not
  change anything else on the computer. It lives in the `venv` folder inside the project.
- **Package**: code written by other people that the app uses, such as Flask. The list of packages
  and their exact versions is in `requirements.txt`.

If `python --version` says *"not recognized"* or opens the Microsoft Store, see
[Troubleshooting](#troubleshooting) before going on.

---

## Step 1: Get the code

**With Git:** open a terminal in the folder where you want the project (for example
`Documents`) and type:

```
git clone https://github.com/JmlAsync/inventory-pos-system.git
cd inventory-pos-system
```

**Without Git:** open https://github.com/JmlAsync/inventory-pos-system, click the green
**Code** button, then **Download ZIP**. Right-click the ZIP, choose **Extract All**, and open
the extracted folder (it is called `inventory-pos-system-main`; Windows sometimes puts it one
folder deeper, inside another folder with the same name). Then open a terminal in that
folder: in File Explorer, click the address bar, type `cmd` and press Enter.

You know you are in the right place when typing `dir` shows `app.py` and `requirements.txt`.

## Step 2: Make the virtual environment

```
python -m venv venv
```

This takes about 10 seconds and prints nothing when it works. A new `venv` folder appears.

## Step 3: Install the packages (needs internet)

```
.\venv\Scripts\python -m pip install -r requirements.txt
```

`.\venv\Scripts\python` means "the Python inside this project's venv". Using it directly means
you never need to *activate* the venv, which PowerShell often blocks on school computers.
The last line should start with `Successfully installed` and list Flask 3.1.3 and SQLAlchemy 2.0.52.

## Step 4 (optional): Bring your own shop's menu and photos

A fresh copy from GitHub has a **generic demo café** with icons instead of photos. That is on
purpose: a real shop's menu, prices and photos are never uploaded to GitHub (rule P1 in
`AGENTS.md`). To show your own menu on this computer:

1. On your own computer, copy the `local_demo` folder (it holds `menu.json` and `photos/`) to a
   USB drive.
2. Paste it into the project folder on this computer, next to `app.py`.

Do this **before** step 5. If you already ran step 5 with the generic menu, run
`.\venv\Scripts\python seed_demo_data.py --fresh` afterwards. On a throwaway copy like this one,
`--fresh` is safe: it only puts this computer's demo database aside. (Never run `--fresh` on the
computer you present from, because it sets your real data aside.)

## Step 5: Fill the database with demo data

```
.\venv\Scripts\python seed_demo_data.py
```

It lists the users, products and ingredients it adds and ends with **`Demo data ready.`**
With your own menu, the first line says `using the local menu in ...`.

## Step 6: Start the app

```
$env:DEMO_MODE = "1"
.\venv\Scripts\python app.py
```

The first line (from v0.28.0) starts the **demo mode**: the demo passwords work, and login codes are shown in this
window instead of being emailed.

Wait for `Running on http://127.0.0.1:5000`. **Leave this window open**: closing it stops the app.
Now open **http://127.0.0.1:5000** in a browser on the same computer.

The app only answers on this computer (`127.0.0.1` means "this computer"), so other computers in
the lab cannot open it.

## Step 7: Log in

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `cashier` | `cashier123` | Cashier |

After the password, type the 6-digit **login code** shown in the app's window (v0.28.0); tick **Trust this device**
to skip it next time. These are the public demo passwords, the same in every fresh copy. Changing them on your own
computer does **not** change them here, because each computer has its own database. If the app will
be left running where others can use it, change them on the **Profile** page.

## Stopping and starting again

- **Stop:** click the terminal window and press **Ctrl + C**.
- **Start again later:** open a terminal in the project folder and repeat **step 6 only**. Steps
  1 to 5 are done once per computer.

---

## Cleaning up a shared computer

The project folder now holds a database, a secret key (`instance/`) and, if you did step 4, your
shop's photos. Before you leave a shared computer:

1. Log out in the browser and close it.
2. Stop the app (Ctrl + C) and close the terminal.
3. Delete the whole project folder (and the ZIP, if you downloaded one).
4. Empty the Recycle Bin.
5. Take your USB drive.

---

## Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `'python' is not recognized...` or the Microsoft Store opens | Python is not installed, or Windows' Store shortcut is in the way | Try `py --version`. If that works, type `py` instead of `python` in step 2 only (steps 3 to 6 use the venv's Python anyway). Otherwise install Python from python.org and tick **"Add python.exe to PATH"** on the first screen; "Install Now" does not need administrator rights. |
| `pip install` hangs, or says `Could not find a version` / `connection` | No internet, or the network blocks package downloads | Use [Plan B](#plan-b-no-internet-on-that-computer). |
| `ERROR: ... requires a different Python` | Python is older than 3.10 | Install Python 3.11 or newer. |
| `Address already in use` / `port 5000 is in use` | Another program uses port 5000 | Start on another port: `.\venv\Scripts\python -m flask --app app run --port 5050`, then open http://127.0.0.1:5050 |
| The page looks old or unstyled after an update | The browser kept the old style sheet | Press **Ctrl + F5** (reload without the saved copy). |
| `The database is in use. Stop the app first` | `--fresh` was run while the app was running | Ctrl + C in the app's window, then run it again. |
| "Too many failed attempts. Please wait..." at log-in | 5 wrong passwords for that username on this computer | Wait the minutes it shows, then try again. |
| `cannot be loaded because running scripts is disabled` | You typed `Activate.ps1`; PowerShell blocks it | You don't need it: use the `.\venv\Scripts\python ...` commands exactly as written above. |

---

## Plan B: no internet on that computer

Download the packages on a computer **with** internet, carry them over on a USB drive, and install
from the drive.

**On the computer with internet** (in the project folder, after step 3 worked there):

```
.\venv\Scripts\python -m pip download -r requirements.txt -d offline_packages --only-binary=:all: --platform win_amd64 --python-version 3.11
```

Change `3.11` to the Python version of the other computer. To cover every version at once, run it
five times with `3.10`, `3.11`, `3.12`, `3.13` and `3.14` (the folder grows to about 13 MB).
Copy the `offline_packages` folder to the USB drive. Do not commit it.

**On the computer without internet**, do steps 1 and 2 (the code can also come from the USB
drive), paste `offline_packages` next to `app.py`, then replace step 3 with:

```
.\venv\Scripts\python -m pip install --no-index --find-links offline_packages -r requirements.txt
```

`--no-index` means "don't go online"; `--find-links` says where the packages are instead. Then
continue with step 4.

---

## macOS and Linux

The steps are the same, with three differences:

- Use `python3` instead of `python` in step 2.
- Use `./venv/bin/python` instead of `.\venv\Scripts\python` everywhere.
- In Plan B, use the platform of that computer (or simply run `pip download -r requirements.txt -d offline_packages` on a computer of the same kind).
