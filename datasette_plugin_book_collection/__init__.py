from datasette import hookimpl, Response, Forbidden, NotFound
from datasette_plugin_book_collection.utils import lookup_book_by_isbn, title_search, lookup_book_by_id, extract_book_from_post_data, save_book, save_book_by_isbn, BookAlreadyExistsError
from datasette.utils import parse_metadata
from datasette_plugin_book_collection.ddl import SETUP_SCRIPT
import asyncio
import sqlite_utils
from starlette.requests import Request as StarletteRequest

# TODO delete this
@hookimpl
def startup(datasette):
    print("datasette-plugin-book-collection startup")
    async def inner():
        config = datasette.plugin_config("datasette-plugin-book-collection")
        if not config:
            return
        for key, target in config.items():
            if key == "database":
                database_name = target
            database = datasette.get_database(database_name)
        print("datasette-plugin-book-collection startup complete, database is: ", database)

    return inner


import click
import sqlite3



    
@hookimpl
def register_commands(cli):
    
    @cli.command()
    @click.argument("files", type=click.Path(), nargs=-1)
    @click.option(
    "-m",
    "--metadata",
    type=click.File(mode="r"),
    help="Path to JSON/YAML file containing license/source metadata",
    )
    @click.argument(
        "isbn", type=click.STRING, nargs=1
    )
    @click.option(
        "--add-new-copy",
        is_flag=True,
        default=False,
        help="Add a new copy of the book even if there is an existing copy.",
    )

    def load_isbn(files, metadata, isbn,  add_new_copy):
        "Load an ISBN from the command line into the database."

        # this can't be imported at the top of the module - datasette.app is loading while its registering commmands
        # but our actual command will run much later after the datasette.app module is done loading
        from datasette.app import Datasette
        if metadata:
            metadata_data = parse_metadata(metadata.read())
        datasette = Datasette(files, metadata=metadata_data)
        config = datasette.plugin_config("datasette-plugin-book-collection")

        if not config:
            return
        for key, target in config.items():
            if key == "database":
                database_name = target
            database = datasette.get_database(database_name)
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(save_book_by_isbn(isbn, database, add_new_copy))
        print(results)
    

    @cli.command()
    @click.argument("files", type=click.Path(), nargs=-1)
    @click.option(
    "-m",
    "--metadata",
    type=click.File(mode="r"),
    help="Path to JSON/YAML file containing license/source metadata",
    )
    def initialize_book_tables(files, metadata):
        "Initialize the book tables in the database."
        from datasette.app import Datasette
        if metadata:
            metadata_data = parse_metadata(metadata.read())
        datasette = Datasette(files, metadata=metadata_data)
        config = datasette.plugin_config("datasette-plugin-book-collection")

        if not config:
            return
        for key, target in config.items():
            if key == "database":
                database_name = target
            database = datasette.get_database(database_name)

        # this feels a little clunky but it creates the main tables and enables the FTS setup
        # i think it's cleaner to do this by letting datasette give me back the database
        # rather than using the 'files' argument?
        # probably not but this works so it's a future TODO to take out this convoluted callback
        # setup
        def enable_fts_helper(conn):
            db = sqlite_utils.Database(conn)
            db.executescript(SETUP_SCRIPT)
            db['book_info'].enable_fts(["title"], create_triggers=True, replace=True)
            db['authors'].enable_fts(["name"], create_triggers=True, replace=True)

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(database.execute_write_fn(enable_fts_helper))
        print("Book tables initialized in database: ", database_name)


def is_valid_isbn(isbn):
    if len(isbn) == 10:
        return True
    if len(isbn) == 13:
        return True
    return False



async def add_new_book(scope, receive, datasette, request):
    db_name = request.args.get("db")
    table_name = request.args.get("table")

    #
    # TODO - should we use the passed in db_name here? 
    # not sure if it would ever make sense to configure this plugin on a per-database basis
    # so for now we assume that the metadata tells us what database to use
    # maybe an alternative would be to have a config item for the plugin that says 'enabled = true' or something
    # none of the routes were setting up are db specific
    #
    try: 
        config = datasette.plugin_config("datasette-plugin-book-collection")
        for key, target in config.items():
                if key == "database":
                    db_name = target

        if not await datasette.permission_allowed(request.actor, "insert-row", (db_name, table_name)):
            raise Forbidden("insert-row permissions required")


        # We will grab all of the authors and pass them to the template
        # which renders them as a datalist so the dropdown can be autocompleted
        db = datasette.get_database(db_name)
        results = await db.execute("SELECT name, author_id, openlibrary_id FROM authors")
        authors = []
        for row in results.rows:
            #authors[row[1]] = row[0]
            authors.append( {'name': row[0], 'author_id': row[1], 'openlibrary_id': row[2]})

        last_location = ""
        results = await db.execute("SELECT location FROM copies order by date_saved desc limit 1")
        for row in results.rows:
            last_location = row[0]
    except Exception as e:
        print("Error setting up page", e)
        return Response.html(
            await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=500)

    if request.method == "POST":
        starlette_request = StarletteRequest(scope, receive)
        data = await starlette_request.form()

        cover_image_data = None
        cover_image_mime_type = None
        if data.get('cover_image_upload', None):
            cover_image = data['cover_image_upload']
            cover_image_mime_type = cover_image.content_type
            cover_image_data = cover_image.file.read()
        book, submitted_authors, copy_info = extract_book_from_post_data(data)
        add_new_copy = False
        if 'add_new_copy' in data:
            add_new_copy = data['add_new_copy'] == 'true'
        try:
            results = await save_book(book, submitted_authors, add_new_copy, copy_info, cover_image_data, cover_image_mime_type, db)
        except BookAlreadyExistsError as e:
            datasette.add_message(request, "Book already exists in the database, but add new copy was not selected.", datasette.ERROR)
            return Response.html(
                await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=409)
        except Exception as e:
            datasette.add_message(request, "Some erorr occured, fix this", datasette.ERROR)
            return Response.html(
                await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=500)
        if results:
            datasette.add_message(request, "Book added successfully.", datasette.INFO)
            # if we have added a new book, update the last location to be that instead of what we last read out of the database
            # it may be null but that's ok, if the user explicitly cleared it let's not reset it but TODO if that's really what we want
            last_location = copy_info.location
            return Response.html(
                await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=200)
        else:
            datasette.add_message(request, "Some erorr occured, fix this", datasette.ERROR)
            return Response.html(
                await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=500)

 

    # This is the GET case, just render the form right now. 
    return Response.html(
            await datasette.render_template('book-collection-add-new-book.html', {'authors':authors, 'last_location': last_location}, request=request), status=200)


async def book_lookup(scope, receive, datasette, request):
    db_name = request.args.get("db")
    table_name = request.args.get("table")

    config = datasette.plugin_config("datasette-plugin-book-collection")
    for key, target in config.items():
            if key == "database":
                db_name = target

    if not await datasette.permission_allowed(request.actor, "view-table", (db_name, table_name)):
        raise Forbidden("view-table permissions required")

    db = datasette.get_database(db_name)

    if request.method == "POST":
        data = await request.post_vars()
        print("book lookup data: ", data)

        if 'isbn' in data and is_valid_isbn(data['isbn']):
            try:
                result = await lookup_book_by_isbn(data['isbn'], db)
                if result:
                    return Response.json(result.model_dump(), status=200)
                else:
                    # TODO  lookup by isbn should be fixed to always return something or except 
                    return Response.json({"message": f"TODO No book with ISBN {data['isbn']} not found."}, status=404)
            except NotFound as e:
                return Response.json({"message": f"No book with ISBN {data['isbn']} not found."}, status=404)
            except ValueError as e:
                return Response.json({"message": f"Problem finding book with ISBN {data['isbn']} - perhaps openlibrary is down?"}, status=503)
            except Exception as e:
                return Response.json({"message": f"Something went wrong while looking for ISBN {data['isbn']}"}, status=500)
        elif 'title' in data:
            pass
        elif 'book_id' in data:
            result = await lookup_book_by_id(data['book_id'], db)
            if result:
                return Response.json(result.model_dump(), status=200)
            else:
                # TODO  lookup by isbn should be fixed to always return something or except 
                return Response.json({"message": f"TODO No book with ID {data['book_id']} not found."}, status=404)

        else:
            return Response.json({"message": "Invalid or missing ISBN."}, status=400)
        
    # fall through if this wasn't a post
    # TODO we don't really just want to redirect here
    return Response.redirect("/-/datasette-book-collection/add-new-book")


async def book_title_search(scope, receive, datasette, request):
    db_name = request.args.get("db")
    table_name = request.args.get("table")

    config = datasette.plugin_config("datasette-plugin-book-collection")
    for key, target in config.items():
            if key == "database":
                db_name = target

    # TODO - this should be a permission check
    if not await datasette.permission_allowed(request.actor, "view-table", (db_name, table_name)):
        raise Forbidden("view-table permissions required")

    db = datasette.get_database(db_name)
    if request.method == "POST":
        data = await request.post_vars()
        if 'title' in data:
            results = await title_search(data['title'], db)
            return Response.json(results, status=200)
        else:
            return None
    # TODO - probably return a 200 and empty list here instead?
    return None

async def cover_image(scope, receive, datasette, request):
    book_id = request.url_vars["book_id"]
    if not book_id:
        raise NotFound("No book id provided for cover image.")
    
    db_name = request.args.get("db")
    table_name = request.args.get("table")

    config = datasette.plugin_config("datasette-plugin-book-collection")
    for key, target in config.items():
            if key == "database":
                db_name = target

    if not await datasette.permission_allowed(request.actor, "view-table", (db_name, table_name)):
        raise Forbidden("view-table permissions required")

    db = datasette.get_database(db_name)
    results = await db.execute("SELECT fullsize, fullsize_mime_type from book_info bi join cover_images ci on bi.cover_image_id = ci.cover_image_id WHERE book_id = :book_id", {"book_id": book_id})
    row = results.first()
    if not row:
        raise NotFound(f"Cover image for book id {book_id} not found.")
    cover_image = row[0]
    mime_type = row[1]
    if not mime_type:
        mime_type = "image/jpeg"
    headers={
                    "content-disposition": 'inline; filename="{}"'.format(
                        "cover_image.jpg"
                    )
                }
    return Response(cover_image, content_type=mime_type, headers=headers, status=200)

@hookimpl
def register_routes():
    return [
        (r"^/-/datasette-book-collection/add-new-book$", add_new_book),
        (r"^/-/datasette-book-collection/book-lookup$", book_lookup),
        (r"^/-/datasette-book-collection/book-title-search$", book_title_search),
        (r"^/-/datasette-book-collection/covers/(?P<book_id>[0-9]+)$", cover_image),
    ]

@hookimpl
def skip_csrf(scope):
    return scope["path"] == "/-/datasette-book-collection/book-lookup" or scope["path"] == "/-/datasette-book-collection/book-title-search"

