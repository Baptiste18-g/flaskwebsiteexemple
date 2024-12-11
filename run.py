from flaskr import create_app
from flaskr.db import init_db, close_db

app = create_app()

with app.app_context():
    init_db()
    print("Initialized the database.")


if __name__ == '__main__':
    app.run(debug=True)