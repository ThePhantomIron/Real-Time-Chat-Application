# Real-Time Chat Application

A desktop real-time chat application built with Python and Tkinter.

## Features

- User registration and login
- Real-time group chat
- Private direct messages
- Delete individual private messages
- Delete private chat threads
- Create, rename, and remove groups
- Voice-to-text input with a mic button
- Local SQLite-backed storage

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
- Windows is the best-supported platform for the current voice input fallback

## Run The App

From the project root:

```bash
python -m chat_app.main
```

You can also run:

```bash
python chat_app/main.py
```

## Notes

- The local database file is intentionally ignored in git: `chat_app/chat.db`
- Editor files and Python cache files are also ignored

## Git

This repository is now initialized with git and can be pushed to GitHub.
