import httpx
import sqlite3
import json
from typing import List, Tuple, Awaitable, Union, Dict, Any
from datetime import datetime

from datasette_plugin_book_collection.ddl import BookInfo, Copy, Author, IsbnLookupResult, OpenLibraryAuthorId, CopyInfoDTO  
from datasette import NotFound

class BookAlreadyExistsError(Exception):
    def __init__(self, message="Book already exists"):
        self.message = message
        super().__init__(self.message)



# Example data
#  {'title': 'Kubeflow for Machine Learning', 'author-name-0': 'Holden Karau', 'author-openlibrary-id-0': 'OL7495916A', 'author-id-0': '', 
#   'author-name-1': 'Trevor Grant', 'author-openlibrary-id-1': 'OL8373616A', 'author-id-1': '', 'author-name-2': 'Ilan Filonenko', 'author-openlibrary-id-2': 'OL8373617A', 'author-id-2': '', 
#   'author-name-3': 'Richard Liu', 'author-openlibrary-id-3': 'OL8373618A', 'author-id-3': '', 'author-name-4': 'Boris Lublinsky', 'author-openlibrary-id-4': 'OL7354008A', 'author-id-4': '', 
#    'isbn': '9781492050124', 'formtype': 'manual', 'csrftoken': 'Indob0FsWjJyd2hCbnBhZW8i.vZQ63ZxXpuZAdGvcQLTSm6TDoWA'}

def extract_authors(post_data: Dict[str, Any]) -> List[Author]:
    authors = {}
    for key, value in post_data.items():
        if key.startswith('author-name-'):
            index = int(key.split('-')[-1])
            if index not in authors:
                authors[index] = Author()
            authors[index].name = value
        elif key.startswith('author-openlibrary-id-'):
            index = int(key.split('-')[-1])
            if index not in authors:
                authors[index] = Author()
            authors[index].openlibrary_id = OpenLibraryAuthorId(id=value)
        elif key.startswith('author-id-'):
            index = int(key.split('-')[-1])
            if index not in authors:
                authors[index] = Author()
            authors[index].author_id = value

    return [author for author in authors.values()]

def extract_book_from_post_data(post_data) -> Tuple[BookInfo, List[Author], CopyInfoDTO]:
    book_data = {}
    book_data['title'] = post_data.get('title', None)
    book_data['isbn_10'] = post_data.get('isbn_10', None)
    # TODO FIXME sort out isbn vs isbn13
    book_data['isbn_13'] = post_data.get('isbn', None)
    book_data['publish_date'] = post_data.get('publish_date', None)
    book_data['publishers'] = post_data.get('publishers', None)
    book_data['openlibrary_edition_id'] = post_data.get('openlibrary_edition_id', None)
    book_data['openlibrary_work_id'] = post_data.get('openlibrary_work_id', None)
    book_data['ratings'] = post_data.get('ratings', None)
    book_data['notes'] = post_data.get('notes', None)
    book_data['location'] = post_data.get('location', None)
    authors = extract_authors(post_data)

    # TODO check for missing data before just returning this
    book_info_object = BookInfo(title=book_data['title'], isbn10=book_data['isbn_10'], isbn13=book_data['isbn_13'], publication_date=book_data['publish_date'], publisher=book_data['publishers'], openlibrary_edition_id=book_data['openlibrary_edition_id'], openlibrary_work_id=book_data['openlibrary_work_id'])
    copy_data_object = CopyInfoDTO(location=book_data['location'], notes=book_data['notes'], ratings=book_data['ratings'])
    return book_info_object, authors, copy_data_object


async def fetch_data_async(url):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True)
            # Always return the status code and the data (which can be None if an error occurs)
            return (response.status_code, response.json() if response.status_code == 200 else None)
        except httpx.HTTPStatusError:
            # In case of HTTP errors, return the status code and None
            return (response.status_code, None)
        except Exception as e:
            # For other exceptions, log the error and return a generic error code with None
            print(f"Error: {str(e)} for {url}")
            return (500, None)

async def fetch_author_data_from_openlibrary(author_keys):
    author_data = []
    for key in author_keys:
        url = f"https://openlibrary.org{key}.json"
        status_code, data = await fetch_data_async(url)
        if status_code == 200 and data:
            author_data.append(data)
    return author_data

async def check_book_exists_typed(db, isbn= None, book_id = None) -> Awaitable[Union[IsbnLookupResult,None]]:
    results = await db.execute("SELECT book_info.book_id, book_info.title, book_info.isbn10, book_info.isbn13, COUNT(*) as copy_count, book_info.title, openlibrary_work_id, openlibrary_edition_id FROM book_info JOIN copies ON book_info.book_id = copies.book_id WHERE isbn13 = ? OR isbn10 = ? OR book_info.book_id = ?", (isbn, isbn, book_id))
    book = results.first()

    # someday setup up a row factory to return something typed from sqlite 
    if book and int(book[4]) > 0:
        results = await db.execute("SELECT authors.author_id, name, openlibrary_id FROM authors JOIN book_author_link ON authors.author_id = book_author_link.author_id WHERE book_id = ?", (book[0],))
        if len(results) > 0:
            authors = [Author(author_id =int(row[0]), name= str(row[1]), openlibrary_id = OpenLibraryAuthorId(id=row[2])) for row in results]
        else:
            authors = []
        
        copies = []
        results = await db.execute("SELECT library_id, book_id, copy_number, location, notes, date_acquired, price, user_cover_image_id, date_saved FROM copies WHERE book_id = ?", (book[0],))
        for row in results: 
            library_id = int(row[0])
            book_id = int(row[1])
            copy_number = int(row[2])
            location=str(row[3]) if row[3] else None
            notes=str(row[4]) if row[4] else None
            date_acquired=str(row[5]) if row[5] else None
            price=float(row[6]) if row[6] else None
            user_cover_image_id=int(row[7]) if row[7] else None
            date_saved=str(row[8]) if row[8] else None
            copies.append(Copy(library_id=library_id, book_id = book_id, copy_number = copy_number, location=location, notes=notes, date_acquired= date_acquired, price=price, user_cover_image_id=user_cover_image_id, date_saved=date_saved))
        return IsbnLookupResult(book=BookInfo(book_id=int(book[0]), title=str(book[1]), isbn10=str(book[2]), isbn13=str(book[3]), openlibrary_work_id = str(book[6]), openlibrary_edition_id=str(book[7])), authors=authors, copies=copies)
    print(f"Looking up book {isbn} by ISBN but don't already have it in the database") 
    return None

async def check_authors_exist(db, author_keys: List[OpenLibraryAuthorId]):
    author_str = ",".join([f'"{author_key}"' for author_key in author_keys])
    results = await db.execute("SELECT author_id, name, openlibrary_id FROM authors WHERE openlibrary_id IN ({})".format(author_str))
    authors = []
    for row in results:
        authors.append(Author(author_id = int(row[0]), name = str(row[1]), openlibrary_id = OpenLibraryAuthorId(id=row[2])))
    return authors


async def insert_authors(db, authors):
    
    author_ids = []
    for author in authors:
        if author.author_id:
            author_ids.append(author.author_id)
            continue

        # TODO let's fix this so when it fails we notice
        author_key = author.openlibrary_id.id
        #print(type(author_key)) - this did not work like we expected
        results = await db.execute("SELECT author_id FROM authors WHERE openlibrary_id = ?", (author_key,))
        existing_author = results.first()

        if existing_author:
            author_ids.append(existing_author[0])
        else:
            # Insert the new author if they don't exist
            #results = await db.execute_write("INSERT INTO authors (name, bio, openlibrary_id) VALUES (?, ?, ?)", 
            #           (author['name'], author.get('bio', ''), author_key))
            # TODO fix the bio its nested sometimes
            results = await db.execute_write("INSERT INTO authors (name, bio, openlibrary_id) VALUES (?, ?, ?)", 
                       (author.name, '', author_key))
            results = await db.execute("SELECT author_id FROM authors WHERE openlibrary_id = ?", (author_key,))
            author_ids.append(results.first()[0])
    return author_ids

async def add_cover_images(db, book_data, copy_info: CopyInfoDTO):
    if not book_data.openlibrary_edition_id:
        return None
    
    cleaned_openlibrary_edition_id = book_data.openlibrary_edition_id.replace("/books/", "")
    m_cover_image_url = f"https://covers.openlibrary.org/b/olid/{cleaned_openlibrary_edition_id}-M.jpg"
    thumbnail_cover_image_url = f"https://covers.openlibrary.org/b/olid/{cleaned_openlibrary_edition_id}-S.jpg"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(m_cover_image_url, follow_redirects=True)
            if response.status_code == 200:
                m_cover_image = response.content

                # alas, openlibrary just returns a 1x1 pixel image if it doesn't have a cover
                # and I don't really feel like adding a dep on an image library to see if it's a 1x1 pixel
                # so we just check if it's a small file and if so assume it's not a real cover image
                if len(m_cover_image) < 1000:
                    m_cover_image = None
            else:
                m_cover_image = None
        except Exception as e:
            print(f"Error fetching cover image: {str(e)}")
            m_cover_image = None
        
        if m_cover_image:
            try:
                results = await db.execute_write("INSERT into cover_images(fullsize, fullsize_mime_type) VALUES (?, ?)", (m_cover_image, "image/jpeg"))
                cover_image_id = results.lastrowid
            except Exception as e:
                print(f"Error inserting cover image: {str(e)}")
                cover_image_id = None
        else:
            cover_image_id = None
    return cover_image_id
        

def new_make_insert_function(book_data, cover_image_id, authors_ids, copy_info: CopyInfoDTO):
    
    def _insert_book_and_link_authors(conn):
        cursor = conn.cursor()
        cursor.execute("INSERT INTO book_info (title, isbn10, isbn13, publication_date, publisher, openlibrary_edition_id, openlibrary_work_id, cover_image_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (book_data.title, book_data.isbn10, book_data.isbn13, book_data.publication_date, book_data.publisher, book_data.openlibrary_edition_id, book_data.openlibrary_work_id, cover_image_id))
        book_id = cursor.lastrowid
        for author_id in authors_ids:
            cursor.execute("INSERT INTO book_author_link (book_id, author_id) VALUES (?, ?)", (book_id, author_id))
        date_saved = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # we only get here if we're the first copy of the book so we can hard code the copy number
        cursor.execute("INSERT INTO copies (book_id, copy_number, date_saved, location, user_cover_image_id) VALUES (?, 1, ?, ?, ?)", (book_id,date_saved, copy_info.location, copy_info.user_cover_image_id))
        conn.commit()
        return cursor.rowcount

    return _insert_book_and_link_authors

async def insert_book_and_authors(db, book_data, authors, copy_info: CopyInfoDTO, user_cover_image_data: bytes, user_cover_image_mime_type: str):
    try:
        author_ids = await insert_authors(db, authors)
    except Exception as e:
        print("Something went wrong in insert authors")
        print(e)
        raise ValueError(f"Failed to insert author data: {e}")

    if len(author_ids) != len(authors):
        print("Failed to insert all authors")
        raise ValueError("Failed to insert all authors")
    
    try:
        results = await add_cover_images(db, book_data, copy_info)
    except Exception as e:
        print("Failed to add cover images")
        print(e)
        raise ValueError(f"Failed to add cover images: {e}")
    if results:
        cover_image_id = results
    else:  
        cover_image_id = None


    user_cover_image_id = None
    if user_cover_image_data:
        try:
            results = await db.execute_write("INSERT into cover_images(fullsize, fullsize_mime_type) VALUES (?, ?)", (user_cover_image_data, user_cover_image_mime_type))
            user_cover_image_id = results.lastrowid
        except Exception as e:
            print(f"Error inserting cover image: {str(e)}")
            user_cover_image_id = None
    copy_info.user_cover_image_id = user_cover_image_id

    # I'm not sure I need all of this extra work - but I think I do, because I need a cursor to get the last row id
    # and db.execute_write doens't do that
    results = await db.execute_write_fn(new_make_insert_function(book_data, cover_image_id, author_ids, copy_info))
    return results



async def save_book(book: BookInfo, authors: List[Author], add_new_copy: bool, copy_info: CopyInfoDTO, user_cover_image_data: bytes, user_cover_image_mime_type: str, db: sqlite3.Connection):
    #cursor = db.cursor()

    isbn = None
    if book.isbn10:
        isbn = book.isbn10
    if book.isbn13:
        isbn = book.isbn13

    existing_copies = await check_book_exists_typed(db, isbn, book.book_id )
    if existing_copies:
        if not add_new_copy:
            raise BookAlreadyExistsError(f"Book already exists: {book.title}")
        else:
            print(f"Saving a new copy! {book.title}")
            user_cover_image_id = None
            if user_cover_image_data:
                try:
                    results = await db.execute_write("INSERT into cover_images(fullsize, fullsize_mime_type) VALUES (?, ?)", (user_cover_image_data, user_cover_image_mime_type))
                    user_cover_image_id = results.lastrowid
                except Exception as e:
                    print(f"Error inserting cover image: {str(e)}")
                    user_cover_image_id = None
            # first we need to get the maximum copy number. existing_copies is an IsbnLookupResult which has a list of copies, so iterate through that list
            # and find the max copy number 
            max_copy_number = max([copy.copy_number for copy in existing_copies.copies])
            try:
                # this runs in a transaction in the datasette library so we don't have to commit it ourselves
                date_saved = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                results = await db.execute_write("INSERT INTO copies (book_id, copy_number, date_saved, location, user_cover_image_id) VALUES (?, ?, ?, ?, ?)", (existing_copies.book.book_id, max_copy_number + 1, date_saved, copy_info.location, user_cover_image_id))
            except Exception as e:
                raise ValueError(f"Failed to add new copy of the book: {e}")
        return True
    
    try:
        # TODO - this used to be more combined but now that it's split it's not a single transaction
        results = await insert_book_and_authors(db, book, authors, copy_info, user_cover_image_data, user_cover_image_mime_type)
    except Exception as e:
        raise ValueError(f"Failed to insert book and author data: {e}")
    if results:
        return True
    return None


#
# TODO this should be much more robust becuase the openlibrary datamodel is kind of complex
# The isbn json always redirects somewhere else - but where is not always consistent
# 
# That said, most (all?) of the time when OL redirects it sends us somewhere that we can get a 'works' key
# and we really should be following that key to the "work" object, getting that from OL
# then looking at the editions and finding the one that matches this ISBN
# that will also give us a more reliable way to find authors, since right now they're sometimes missing
# from just the ediition object if that's where a particular isbn redirects us
async def openlibrary_isbn_lookup(db, isbn):

    status_code, book_data = await fetch_data_async(f"https://openlibrary.org/isbn/{isbn}.json")
    if status_code == 404:
        #return {"message": f"Unable to find book with ISBN {isbn}", "status": 404, "message_code": "isbn_404"}
        raise NotFound(f"Unable to find book with ISBN {isbn}")
    elif status_code != 200 or not book_data:
        raise ValueError("Failed to fetch book data for ISBN {isbn}")
        #return {"message": "Failed to fetch book data.", "message_code": "generic_error", "status": 500}
    
    openlibrary_work_id = book_data.get('works', [{}])[0].get('key', None)

    # verify that this is an edition object
    openlibrary_edition_id = None
    # this feels very non pythonic
    if 'type' in book_data and 'key' in book_data['type'] and book_data['type']['key'] == '/type/edition':
        openlibrary_edition_id = book_data.get('key', None)
    # these are json fields with /author/OLxxxxx formatted keys
    # the fetch_author_data_from_openlibrary function just passes them right to the endopint
    # TODO openlibrary is a disaster on how they handle authors and half the time it's missing
    existing_authors = []
    if 'authors' in book_data:
        raw_author_keys = [author['key'] for author in book_data['authors']]
        openlibrary_authors_data = await fetch_author_data_from_openlibrary(raw_author_keys)
        if not openlibrary_authors_data:
            raise ValueError("Failed to fetch author data.")
            #return {"message": "Failed to fetch author data.", "message_code": "generic_error", "status":500}
    
        # when we store an author we keep 
        openlibrary_author_ids = [key.split('/')[-1] for key in raw_author_keys]  # Extracting the ID from the URL path
        existing_authors = await check_authors_exist(db, openlibrary_author_ids)
        existing_author_ids = {author.openlibrary_id for author in existing_authors}


        # Step 2: Iterate over the authors_data list
        for author_data in openlibrary_authors_data:
        # Extract the openlibrary_id by removing the '/authors/' prefix
            openlibrary_id = author_data['key'].split('/')[-1]

            # Step 3: Check if the author is not in the existing_author_ids set
            if OpenLibraryAuthorId(id=openlibrary_id) not in existing_author_ids:
                # Step 4: Create a new Author object (assuming an Author class exists)
                # Note: The Author class constructor and attributes might need to be adjusted based on actual implementation
                new_author = Author(name=author_data['name'], openlibrary_id=OpenLibraryAuthorId(id=openlibrary_id))

                # Step 5: Append the new Author object to the existing_authors list
                existing_authors.append(new_author)

    #return IsbnLookupResult(book=BookInfo(book_id=int(book[0]), title=str(book[1]), isbn10=str(book[2]), isbn13=str(book[3])), authors=authors)
    print("book data: ", book_data.get('isbn_13', [None])[0])

    return IsbnLookupResult(book=BookInfo(title=book_data['title'], openlibrary_work_id = openlibrary_work_id, openlibrary_edition_id = openlibrary_edition_id, isbn10=next(iter(book_data.get('isbn_10', [])), None), isbn13=next(iter(book_data.get('isbn_13', [])), None)), authors=existing_authors, copies=[])
    
    

async def lookup_book_by_isbn(isbn, db)-> Awaitable[Union[IsbnLookupResult,None]]:
    results = await check_book_exists_typed(db, isbn)
    if not results:
        try:
            results = await openlibrary_isbn_lookup(db, isbn)   
        except NotFound as e:
            raise e
        except ValueError as e:
            print(f"ValueError in lookup_book_by_isbn: {str(e)}")
            raise e
        except Exception as e:
            print(f"Error in lookup_book_by_isbn: {str(e)}")
            return None

    if results:
        return results
    else:
        return None

async def lookup_book_by_id(book_id, db)-> Awaitable[Union[IsbnLookupResult,None]]:
    results = await check_book_exists_typed(db,isbn=None, book_id=book_id)
    if not results:
        return None
    return results

async def title_search(title, db):
    results = await db.execute('select book_id, title from book_info where rowid in (select rowid from book_info_fts where book_info_fts match escape_fts(?) || "*") order by book_id limit 101'    , (f"%{title}%",))
    matches = []
    for row in results:
        book_match = {}
        book_match['book_id'] = row[0]
        book_match['title'] = row[1]
        matches.append(book_match)
    return matches

# There is no web route for this anymore but you can do it from the command line
async def save_book_by_isbn(isbn: str, db: sqlite3.Connection, add_new_copy: bool = False) -> Awaitable[Union[IsbnLookupResult, None]]:
    try:
        book_data = await lookup_book_by_isbn(isbn, db)
        if not book_data:
            return None
        copy_info = CopyInfoDTO() # someday we'll take commandline args for this
        await save_book(book_data.book, book_data.authors, add_new_copy, copy_info, user_cover_image_data = None, user_cover_image_mime_type = None, db=db)
        return True
    
    # TODO I might want to just throw these again
    except BookAlreadyExistsError as e:
        print(f"Book already exists: {e}")
        return None
    except NotFound as e:
        print(f"Book not found: {e}")
        return None
    except Exception as e:
        print(f"Error in save_book_by_isbn: {str(e)}")
        return None