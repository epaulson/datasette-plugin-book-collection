from pydantic import BaseModel, field_validator, ValidationError
from typing import List, Optional


class OpenLibraryAuthorId(BaseModel):
    id: str

    @field_validator('id')
    def key_must_start_with_OL_and_have_no_slashes(cls, value):
        if not value.startswith("OL"):
            raise ValueError("Key must start with 'OL'")
        if "/" in value:
            raise ValueError("Key must not contain '/' characters")
        return value
    
    def __str__(self):
        return self.id
    
    def __repr__(self):
        return f"OpenLibraryAuthorId(key={self.id})"
    
    def __eq__(self, other):
        if not isinstance(other, OpenLibraryAuthorId):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
    
class Author(BaseModel):
    author_id: Optional[int] = None
    openlibrary_id: Optional[OpenLibraryAuthorId] = None
    name: Optional[str] = None
    bio: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.name} ({self.openlibrary_id}) - {self.author_id}"
    
    def __repr__(self) -> str:
        return f"Author(author_id={self.author_id}, openlibrary_id={self.openlibrary_id}, name={self.name}"
    

class BookInfo(BaseModel):
    book_id: Optional[int] = None
    title: str
    openlibrary_edition_id: Optional[str] = None
    openlibrary_work_id: Optional[str] = None
    publication_date: Optional[str] = None
    publisher: Optional[str] = None
    isbn10: Optional[str] = None
    isbn13: Optional[str] = None
    ratings: Optional[int] = None
    notes: Optional[str] = None
    classifications: Optional[str] = None
    cover_image_id: Optional[int] = None
    cover_image_openlibrary_id: Optional[str] = None

#TODO this needs a better name
class CopyInfoDTO(BaseModel):
    location: Optional[str] = None
    notes: Optional[str] = None
    date_acquired: Optional[str] = None
    price: Optional[float] = None
    user_cover_image_id: Optional[int] = None

class Copy(BaseModel):
    library_id: int
    book_id: int
    copy_number: int
    location: Optional[str] = None
    notes: Optional[str] = None
    date_acquired: Optional[str] = None
    price: Optional[float] = None
    user_cover_image_id: Optional[int] = None
    date_saved: str

class CoverImage(BaseModel):
    cover_image_id: int
    fullsize: Optional[bytes] = None
    thumbnail: Optional[bytes] = None
    fullsize_mime_type: Optional[str] = None
    thumbnail_mime_type: Optional[str] = None

class Library(BaseModel):
    library_id: int
    book_id: int
    copy_number: int
    location: str
    copy_notes: str
    date_acquired: str
    date_saved: str
    price: float
    user_cover_image_id: int
    title: str
    openlibrary_edition_id: str
    openlibrary_work_id: str
    publication_date: str
    publisher: str
    isbn10: str
    isbn13: str
    ratings: int
    book_notes: str
    classifications: str
    cover_image_id: int
    authors: List[Author]

class IsbnLookupResult(BaseModel):
    book: BookInfo
    authors: List[Author]
    copies: List[Copy]


SETUP_SCRIPT = """
-- SQL script to initialize a personal library database with updated requirements

-- Drop existing tables if they exist
DROP TABLE IF EXISTS book_info;
DROP TABLE IF EXISTS authors;
DROP TABLE IF EXISTS copies;
DROP TABLE IF EXISTS cover_images;
DROP TABLE IF EXISTS book_author_link;

-- Create the authors table
CREATE TABLE authors (
    author_id INTEGER PRIMARY KEY,
    openlibrary_id TEXT,
    name TEXT NOT NULL,
    bio TEXT
);

-- Create the bibliographic table: book_info
CREATE TABLE book_info (
    book_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    openlibrary_edition_id TEXT,
    openlibrary_work_id TEXT,
    publication_date TEXT, -- Storing as TEXT in ISO8601 format
    publisher TEXT,
    isbn10 TEXT,
    isbn13 TEXT,
    ratings INTEGER,
    notes TEXT,
    classifications TEXT, -- Storing classifications as a JSON array in a TEXT column
    cover_image_id INTEGER,
    cover_image_openlibrary_id TEXT,
    FOREIGN KEY (cover_image_id) REFERENCES cover_images(cover_image_id)
);

-- Recreate the copies table with the new structure
CREATE TABLE copies (
    library_id INTEGER PRIMARY KEY,
    book_id INTEGER,
    copy_number INTEGER NOT NULL,
    location TEXT,
    notes TEXT,
    date_acquired TEXT, -- Storing as TEXT in ISO8601 format
    price REAL, -- Price column as requested
    user_cover_image_id INTEGER,
    date_saved TEXT, -- Storing as TEXT in ISO8601 format
    FOREIGN KEY (book_id) REFERENCES book_info(book_id),
    FOREIGN KEY (user_cover_image_id) REFERENCES cover_images(cover_image_id),
    UNIQUE(book_id, copy_number) -- Ensuring that each copy number is unique per book
);

-- Create the cover images table
CREATE TABLE cover_images (
    cover_image_id INTEGER PRIMARY KEY,
    fullsize BLOB,
    thumbnail BLOB,
    fullsize_mime_type TEXT,
    thumbnail_mime_type TEXT
);

-- Create the book_author_link table for many-to-many relationship between books and authors
CREATE TABLE book_author_link (
    book_id INTEGER,
    author_id INTEGER,
    PRIMARY KEY (book_id, author_id),
    FOREIGN KEY (book_id) REFERENCES book_info(book_id),
    FOREIGN KEY (author_id) REFERENCES authors(author_id)
);

DROP VIEW IF EXISTS library;

CREATE VIEW library AS
SELECT 
    c.library_id,
    c.book_id,
    c.copy_number,
    c.location,
    c.notes AS copy_notes,
    c.date_acquired,
    c.price,
    c.user_cover_image_id,
    b.title,
    b.openlibrary_edition_id,
    b.openlibrary_work_id,
    b.publication_date,
    b.publisher,
    b.isbn10,
    b.isbn13,
    b.ratings,
    b.notes AS book_notes,
    b.classifications,
    b.cover_image_id,
    c.date_saved,
    (
    SELECT json_group_array(a.name)
    FROM book_author_link bal
    JOIN authors a ON bal.author_id = a.author_id
    WHERE bal.book_id = b.book_id
) AS authors
FROM copies c
JOIN book_info b ON c.book_id = b.book_id;
"""