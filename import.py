import csv, os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
                                                    
db = scoped_session(sessionmaker(bind=engine)) 

b = open("books.csv")
reader = csv.reader(b)
for i, tit, auth, y in reader:
    db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)", {"isbn": i, "title": tit, "author": auth, "year": y}) 
    db.commit()