# Real-Time Chat Application

A desktop real-time chat application built with Python and Tkinter.

## Features

- User registration and login
- Real-time group chat
- Private direct messages
- Delete individual private messages
- Delete private chat threads
- Create, rename, and remove groups
- One PC can host and multiple PCs can join the same chat over a local network
- Local SQLite-backed storage on the host machine

## Project Structure

```text
chat_app/
  app.py
  main.py
  server.py
  core/
  network/
  ui/
```

## Requirements

- Python 3.13 recommended
- All PCs should be on the same LAN or Wi-Fi network for shared chat

## Run The App

From the project root:

```bash
python -m chat_app.main
```

You can also run:

```bash
python chat_app/main.py
```

## Share One Chat Across Multiple PCs

1. On the host PC, run the app and enable `Host chat on this PC`.
2. Note the IP address shown on the login screen.
3. On every other PC, run the app and enter the shared `Server Name` or the host PC name/IP, plus the shared `Server Password`.
4. Log in or register on the shared host.

You can also run only the server on the host PC:

```bash
python -m chat_app.server
```

## Notes

- The local database file is intentionally ignored in git: `chat_app/chat.db`
- Shared chat history lives on the host PC because SQLite runs there
- `Server Name` now supports LAN discovery when the host and joiners are on the same local network
- Windows Firewall may ask for permission the first time the host accepts LAN connections
- Editor files and Python cache files are also ignored

## Git

This repository is now initialized with git and can be pushed to GitHub.
