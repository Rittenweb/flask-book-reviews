import os
import requests

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    # Checks whether the user is logged in.
    if session.get("user_id") is None:
        return render_template("index.html")
    else:
        return render_template("search.html", username=db.execute("SELECT * FROM users WHERE id = :id", {"id": session.get("user_id")}).fetchone().username)

@app.route("/logout")
def logout():
    session.clear()
    return render_template("index.html")

@app.route("/registration", methods=["POST"])
def registration():
    username = request.form.get("usernameregister")
    password = request.form.get("passwordregister")
    if username == None or password == None:
        return render_template("error.html", message="Fill out both fields.")
    if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount != 0:
        return render_template("registration.html", taken=True)
    else:
        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": password})
        db.commit()
        return render_template("registration.html", taken=False)


@app.route("/search", methods=["GET", "POST"])
def search():
    username = request.form.get("usernamelogin")
    password = request.form.get("passwordlogin")
    #If user is trying to login, try to log them in
    if session.get("user_id") is None:
        if username == None or password == None:
            return render_template("error.html", message="Fill out both fields.")
        elif db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone().password != password:
            return render_template("error.html", message="Wrong login info.")
        else:
            session["user_id"] = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone().id
            return render_template("search.html", username=username)
    #If user is already logged in, check if they are searching
    else:
        searchterm = request.form.get("searchterm")
        username = db.execute("SELECT * FROM users WHERE id = :id", {"id": session.get("user_id")}).fetchone().username
        if searchterm == None:
            return render_template("search.html", username=username)
        else:
            if request.form.get("searchby") == "isbn":
                searchresults = db.execute("SELECT * FROM books WHERE isbn iLIKE '%" + searchterm + "%'").fetchall()
            elif request.form.get("searchby") == "author":
                searchresults = db.execute("SELECT * FROM books WHERE author iLIKE '%" + searchterm + "%'").fetchall()
            elif request.form.get("searchby") == "title":
                searchresults = db.execute("SELECT * FROM books WHERE title iLIKE '%" + searchterm + "%'").fetchall()
            else:
                return render_template("error.html", message="Enter searchby parameters.")
            return render_template("search.html", username=username, searched=True, books=searchresults)


@app.route("/book/<int:book_id>", methods=["GET", "POST"])
def book(book_id):
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", message="Non-existent.")
    if request.method == "POST" and request.form.get("rating") != None:
        db.execute("INSERT INTO reviews (book_id, user_id, rating, text, timestamp) VALUES (:book_id, :user_id, :rating, :text, :timestamp)", {"book_id": book_id, "user_id": session.get("user_id"), "rating": request.form.get("rating"), "text": request.form.get("reviewtext"), "timestamp": datetime.now()})
        db.commit()
    if db.execute("SELECT * FROM reviews WHERE user_id = :userid AND book_id = :bookid", {"userid": session.get("user_id"), "bookid": book_id}).rowcount == 0:
        notreviewed = True
    else:
        notreviewed = False
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "C2uCWlOrwroxbM8zDQDm8Q", "isbns": book.isbn})
    if res.status_code != 200:
        gravg = "N/A"
        grcount = "N/A"
    else:
        data = res.json()
        gravg = data["books"][0]["average_rating"]
        grcount = data["books"][0]["work_ratings_count"]
    reviews = db.execute("SELECT username, rating, timestamp, text FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :bookid", {"bookid": book_id}).fetchall()
    return render_template("book.html", book=book, notreviewed=notreviewed, reviews=reviews, gravg=gravg, grcount=grcount)

@app.route("/api/<isbn>")
def book_api(isbn):

    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return jsonify({"error": "ISBN not present in database"}), 404

    # Calculate two database values
    count = db.execute("SELECT * FROM reviews WHERE book_id = :id", {"id": book.id}).rowcount
    avg = db.execute("SELECT CAST(AVG(rating) as FLOAT) FROM reviews WHERE book_id = :id", {"id": book.id}).fetchone().avg

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": isbn,
        "review_count": count,
        "review_score": avg
        })