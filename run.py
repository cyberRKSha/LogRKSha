import uvicorn
import os
import atexit

LOCK_FILE = "webapp.lock"

def create_lock_file():
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    print(f"Webapp lock file created: {LOCK_FILE}")

def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print(f"Webapp lock file removed: {LOCK_FILE}")

if __name__ == "__main__":
    create_lock_file()
    atexit.register(remove_lock_file)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
