from datasette.app import Datasette
import pytest
import json
from datasette_plugin_book_collection.ddl import SETUP_SCRIPT
from datasette_plugin_book_collection.ddl import IsbnLookupResult
from datasette_plugin_book_collection.utils import save_book_by_isbn, lookup_book_by_isbn, save_book
import httpx
import sqlite_utils


test_metadata={
  "plugins": {
    "datasette-plugin-book-collection": { "database" : "test"}
   }
}

# https://openlibrary.org/isbn/9781593277574.json
understanding_ecmascript6_json = """
{"publishers": ["No Starch Press"], "source_records": ["amazon:1593277571", "marc:marc_openlibraries_sanfranciscopubliclibrary/sfpl_chq_2018_12_24_run05.mrc:367891929:2119", "bwb:9781593277574", "promise:bwb_daily_pallets_2023-01-11", "marc:marc_nuls/NULS_PHC_180925.mrc:124573029:1302", "ia:understandingecm0000zaka"], "title": "Understanding ECMAScript 6: The Definitive Guide for JavaScript Developers", "isbn_10": ["1593277571"], "number_of_pages": 352, "covers": [8512695], "local_id": ["urn:sfpl:31223118732099", "urn:sfpl:31223118732107", "urn:bwbsku:T2-FPJ-398"], "isbn_13": ["9781593277574"], "lc_classifications": ["QA76.73.J39Z3575", "QA76.73.J39 Z3575 2016"], "publish_date": "Aug 16, 2016", "key": "/books/OL26837232M", "authors": [{"key": "/authors/OL1432776A"}], "works": [{"key": "/works/OL19546642W"}], "type": {"key": "/type/edition"}, "lccn": ["2016021923"], "oclc_numbers": ["955274352"], "ocaid": "understandingecm0000zaka", "latest_revision": 7, "revision": 7, "created": {"type": "/type/datetime", "value": "2019-04-05T17:43:51.862156"}, "last_modified": {"type": "/type/datetime", "value": "2023-07-12T04:32:54.664851"}}
"""

# https://openlibrary.org/isbn/9780134610993.json
russell_norvig_json = """
{"publishers":["Pearson"],"subtitle":"A Modern Approach","covers":[13530046,9386859],"physical_format":"paperback","full_title":"Artificial Intelligence A Modern Approach","key":"/books/OL28002220M","authors":[{"key":"/authors/OL440500A"},{"key":"/authors/OL772166A"}],"source_records":["amazon:0134610997","bwb:9780134610993","marc:marc_columbia/Columbia-extract-20221130-031.mrc:294034301:1740","idb:9780134610993"],"title":"Artificial Intelligence","notes":"Source title: Artificial Intelligence: A Modern Approach (4th Edition)","number_of_pages":1136,"publish_date":"May 08, 2020","works":[{"key":"/works/OL2896994W"}],"type":{"key":"/type/edition"},"identifiers":{},"isbn_10":["0134610997"],"isbn_13":["9780134610993"],"lccn":["2019047498"],"oclc_numbers":["1124776132"],"classifications":{},"lc_classifications":["Q335","Q335 .R86 2021"],"latest_revision":8,"revision":8,"created":{"type":"/type/datetime","value":"2020-05-05T11:39:53.447995"},"last_modified":{"type":"/type/datetime","value":"2023-12-19T20:45:56.421020"}}
"""
russell_author_json = """
{"name": "Stuart J. Russell", "remote_ids": {"viaf": "81856176", "wikidata": "Q3656334", "isni": "0000000083978047"}, "key": "/authors/OL440500A", "personal_name": "Stuart J. Russell", "photos": [12855436, 12855435], "type": {"key": "/type/author"}, "alternate_names": ["Stuart Russell"], "latest_revision": 9, "revision": 9, "created": {"type": "/type/datetime", "value": "2008-04-01T03:28:50.625462"}, "last_modified": {"type": "/type/datetime", "value": "2022-08-10T16:59:15.998431"}}
"""
norvig_author_json = """
{"type": {"key": "/type/author"}, "source_records": ["amazon:2744071501"], "personal_name": "Peter Norvig", "key": "/authors/OL772166A", "name": "Peter Norvig", "photos": [8085718], "alternate_names": ["Peter NORVIG", "NUO WEI GE"], "remote_ids": {"wikidata": "Q92832"}, "latest_revision": 6, "revision": 6, "created": {"type": "/type/datetime", "value": "2008-04-01T03:28:50.625462"}, "last_modified": {"type": "/type/datetime", "value": "2023-10-16T21:31:15.378290"}}
"""

# https://openlibrary.org/authors/OL1432776A.json
zakas_author_json = """
{"name": "Nicholas C. Zakas", "personal_name": "Nicholas C. Zakas", "key": "/authors/OL1432776A", "type": {"key": "/type/author"}, "photos": [14421164], "latest_revision": 3, "revision": 3, "created": {"type": "/type/datetime", "value": "2008-04-01T03:28:50.625462"}, "last_modified": {"type": "/type/datetime", "value": "2023-09-12T12:58:51.075293"}}
"""

# https://openlibrary.org/isbn/9781801819312.json - Machine Learning with Pytorch and scikit-learn (4 authors test)
ml_with_pytorch_json = """
{"type": {"key": "/type/edition"}, "authors": [{"key": "/authors/OL7246580A"}, {"key": "/authors/OL7495021A"}, {"key": "/authors/OL7495683A"}, {"key": "/authors/OL10269287A"}], "isbn_13": ["9781801819312"], "languages": [{"key": "/languages/eng"}], "pagination": "770", "publish_date": "2022", "publishers": ["Packt Publishing, Limited"], "source_records": ["bwb:9781801819312", "amazon:1801819319", "idb:9781801819312", "promise:bwb_daily_pallets_2024-04-30:P9-DXK-167"], "title": "Machine Learning with Pytorch and Scikit-Learn", "subtitle": "Develop Machine Learning and Deep Learning Models with Python", "works": [{"key": "/works/OL27412373W"}], "key": "/books/OL37335350M", "number_of_pages": 771, "local_id": ["urn:bwbsku:P9-DXK-167"], "latest_revision": 4, "revision": 4, "created": {"type": "/type/datetime", "value": "2022-02-28T09:50:07.093121"}, "last_modified": {"type": "/type/datetime", "value": "2024-05-15T20:15:19.919166"}}
"""

# https://openlibrary.org/isbn/9781718503762.json - machine learning q&a (1 author test)
ml_qa_json = """
{"type": {"key": "/type/edition"}, "authors": [{"key": "/authors/OL7246580A"}], "isbn_13": ["9781718503762"], "languages": [{"key": "/languages/eng"}], "lc_classifications": ["Q335.R37 2024"], "pagination": "232", "publish_date": "2024", "publishers": ["No Starch Press, Incorporated"], "source_records": ["bwb:9781718503762"], "subjects": ["Science"], "title": "Machine Learning and AI Beyond the Basics", "weight": "0.369", "works": [{"key": "/works/OL37618508W"}], "key": "/books/OL50714972M", "latest_revision": 1, "revision": 1, "created": {"type": "/type/datetime", "value": "2024-01-31T07:08:33.160304"}, "last_modified": {"type": "/type/datetime", "value": "2024-01-31T07:08:33.160304"}}
"""

#https://openlibrary.org/authors/OL7246580A.json
seb_raska_author_json = """
{"name": "Sebastian Raschka", "created": {"type": "/type/datetime", "value": "2015-10-21T01:55:11.273004"}, "last_modified": {"type": "/type/datetime", "value": "2015-10-21T01:55:11.273004"}, "latest_revision": 1, "key": "/authors/OL7246580A", "type": {"key": "/type/author"}, "revision": 1}
"""
# https://openlibrary.org/authors/OL7495021A.json
hayden_liu_author_json = """
{"name": "Yuxi (Hayden) Liu", "created": {"type": "/type/datetime", "value": "2019-04-05T00:05:45.231690"}, "last_modified": {"type": "/type/datetime", "value": "2019-04-05T00:05:45.231690"}, "latest_revision": 1, "key": "/authors/OL7495021A", "type": {"key": "/type/author"}, "revision": 1}
"""

# https://openlibrary.org/authors/OL7495683A.json
vahid_mirjalili_author_json = """
{"name": "Vahid Mirjalili", "created": {"type": "/type/datetime", "value": "2019-04-05T02:43:27.078014"}, "last_modified": {"type": "/type/datetime", "value": "2019-04-05T02:43:27.078014"}, "latest_revision": 1, "key": "/authors/OL7495683A", "type": {"key": "/type/author"}, "revision": 1}
"""

# https://openlibrary.org/authors/OL10269287A.json
dmytro_dzhulgakov_author_json = """
{"type": {"key": "/type/author"}, "name": "Dmytro Dzhulgakov", "key": "/authors/OL10269287A", "source_records": ["bwb:9781801819312"], "latest_revision": 1, "revision": 1, "created": {"type": "/type/datetime", "value": "2022-02-28T09:50:07.093121"}, "last_modified": {"type": "/type/datetime", "value": "2022-02-28T09:50:07.093121"}}
"""

# https://openlibrary.org/isbn/9780134034287.json
effective_python_1st_edition_json = """
{"publishers": ["Addison-Wesley"], "identifiers": {}, "subtitle": "59 specific ways to write better Python.", "weight": "1.0 pounds", "series": ["Effective Software Development Series"], "covers": [7363706], "physical_format": "Paperback", "lc_classifications": ["QA76.73.P98S57 2015", "QA76.73.P98 S57 2015"], "key": "/books/OL25764006M", "publish_places": ["Indianapolis, USA"], "isbn_13": ["9780134034287"], "classifications": {}, "source_records": ["amazon:0134034287", "marc:marc_openlibraries_sanfranciscopubliclibrary/sfpl_chq_2018_12_24_run05.mrc:171447201:4892", "bwb:9780134034287", "marc:marc_loc_2016/BooksAll.2016.part41.utf8:212878937:898", "marc:marc_columbia/Columbia-extract-20221130-025.mrc:220742638:3686"], "title": "Effective Python", "lccn": ["2014048305"], "number_of_pages": 256, "languages": [{"key": "/languages/eng"}], "local_id": ["urn:sfpl:31223113480793", "urn:sfpl:31223113480801", "urn:sfpl:31223116650806", "urn:sfpl:31223116650798", "urn:sfpl:31223116692113", "urn:sfpl:31223116692105"], "publish_date": "2015", "copyright_date": "2015", "works": [{"key": "/works/OL17192267W"}], "type": {"key": "/type/edition"}, "physical_dimensions": "9.1 x 0.6 x 7.0 inches", "oclc_numbers": ["898408310"], "latest_revision": 9, "revision": 9, "created": {"type": "/type/datetime", "value": "2015-08-31T17:15:12.744406"}, "last_modified": {"type": "/type/datetime", "value": "2022-12-20T16:06:03.965626"}}
"""
# https://openlibrary.org/isbn/9780134610999.json
# TODO openlibrary doesn't seem to give back json for a missing book





@pytest.fixture
def non_mocked_hosts():
    # This ensures httpx-mock will not affect Datasette's own
    # httpx calls made in the tests by datasette.client:
    return ["localhost"]


@pytest.fixture(scope="session")
def datasette(tmp_path_factory):
    db_directory = tmp_path_factory.mktemp("dbs")
    db_path = db_directory / "test.db"
    db = sqlite_utils.Database(db_path)
    db.executescript(SETUP_SCRIPT)
    db['book_info'].enable_fts(["title"], create_triggers=True, replace=True)
    datasette = Datasette(
        [db_path],
        metadata=test_metadata
    )
    return datasette

@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-plugin-book-collection" in installed_plugins


@pytest.mark.asyncio
async def test_lookup_by_isbn_internal(datasette, httpx_mock):

    httpx_mock.add_response(
        url="https://openlibrary.org/isbn/9780134610993.json",
        json=json.loads(russell_norvig_json),
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL440500A.json",
        json=json.loads(russell_author_json),
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL772166A.json",
        json=json.loads(norvig_author_json),
        headers={"content-type": "application/json"},
    )

    db = datasette.get_database("test")
    # TODO let check a better result than just it was true
    results = await lookup_book_by_isbn("9780134610993", db=db)
    assert results, f"Assertion failed, results contents: {results}"


@pytest.mark.asyncio
async def test_import_book_by_isbn_internal(datasette, httpx_mock):

    httpx_mock.add_response(
        url="https://openlibrary.org/isbn/9780134610993.json",
        json=json.loads(russell_norvig_json),
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL440500A.json",
        json=json.loads(russell_author_json),
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL772166A.json",
        json=json.loads(norvig_author_json),
        headers={"content-type": "application/json"},
    )

    db = datasette.get_database("test")
    results = await save_book_by_isbn("9780134610993", db=db, add_new_copy=False)
    assert results, f"Assertion failed, results contents: {results}"

 
@pytest.mark.asyncio
async def test_fetch_authors(datasette):
    response = await datasette.client.get("/test/authors.json")
    assert response.status_code == 200
    results = response.json()
    print(results)
    authors = []
    for row in results['rows']:
        authors.append(row['name'])
    print(authors)
    assert 'Stuart J. Russell' in authors
    assert 'Peter Norvig' in authors
    assert 'Donald Trump' not in authors


@pytest.mark.asyncio
async def test_regular_book_insert(datasette, httpx_mock):
   

    #httpx_mock.add_response(
    #    url="https://openlibrary.org/isbn/9781593277574.json",
    #    json=json.loads(understanding_ecmascript6_json),
    #    headers={"content-type": "application/json"},
    #)
    #httpx_mock.add_response(
    #    url="https://openlibrary.org/authors/OL1432776A.json",
    #    json=json.loads(zakas_author_json),
    #    headers={"content-type": "application/json"},
    #)

    cookies = {"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")}
    response = await datasette.client.get("/-/datasette-book-collection/add-new-book", cookies=cookies)
    assert response.status_code == 200
    csrftoken = response.cookies["ds_csrftoken"]
    cookies["ds_csrftoken"] = csrftoken
    response = await datasette.client.post(
        "/-/datasette-book-collection/add-new-book",
        data={
            "isbn": "9781593277574",
            "title": "Understanding ECMAScript 6: The Definitive Guide for JavaScript Developers",
            "author-name-1": "Nicholas C. Zakas",
            "author-openlibrary-id-1": "OL1432776A",
            "csrftoken": csrftoken,
            "formtype": "lookup",
            "add_new_copy": "false"
        },
        cookies=cookies,
    )
    print(response)
    print(response.status_code)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_fetch_books(datasette):
    response = await datasette.client.get("/test/library.json")
    assert response.status_code == 200
    results = response.json()
    books = []
    for row in results['rows']:
        books.append(row['title'])

    assert len(books) == 2
    assert 'Understanding ECMAScript 6: The Definitive Guide for JavaScript Developers' in books
    assert 'Artificial Intelligence' in books


@pytest.mark.asyncio
async def test_lookup_via_isbn(datasette):
    response = await datasette.client.post("/-/datasette-book-collection/book-lookup", data={"isbn": "9780134610993"})
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    results = response.json()
    from_json = IsbnLookupResult.model_validate(results)
    assert from_json
    assert from_json.book.title == 'Artificial Intelligence'
    assert len(from_json.authors) == 2
    assert from_json.authors[0].name == 'Stuart J. Russell' or from_json.authors[1].name == 'Stuart J. Russell'


@pytest.mark.asyncio
async def test_lookup_missing_book_via_isbn(datasette, httpx_mock):
    httpx_mock.add_response(
        url="https://openlibrary.org/isbn/9780134610999.json",
        status_code = 404,
        headers={"content-type": "application/json"},
    )
     
    response = await datasette.client.post("/-/datasette-book-collection/book-lookup", data={"isbn": "9780134610999"})
    assert response.status_code == 404, f"Unexpected status code: {response.status_code}"


@pytest.mark.asyncio
async def test_lookup_invalid_book_via_isbn(datasette):
    response = await datasette.client.post("/-/datasette-book-collection/book-lookup", data={"isbn": "9780"})
    assert response.status_code == 400, f"Unexpected status code: {response.status_code}"

@pytest.mark.asyncio
async def test_lookup_book_with_no_authors(datasette, httpx_mock):
    httpx_mock.add_response(
        url="https://openlibrary.org/isbn/9780134034287.json",
        json=json.loads(effective_python_1st_edition_json),
        headers={"content-type": "application/json"},
    )
    response = await datasette.client.post("/-/datasette-book-collection/book-lookup", data={"isbn": "9780134034287"})
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    results = response.json()
    from_json = IsbnLookupResult.model_validate(results)
    assert from_json
    assert from_json.book.title == 'Effective Python'
    assert len(from_json.authors) == 0

        
@pytest.mark.asyncio
async def test_insert_one_seb_book(datasette, httpx_mock):
    #httpx_mock.add_response(
    #    url="https://openlibrary.org/isbn/9781718503762.json",
    #    json=json.loads(ml_qa_json),
    #    headers={"content-type": "application/json"},
    #)
    #httpx_mock.add_response(
    #    url="https://openlibrary.org/authors/OL7246580A.json",
    #    json=json.loads(seb_raska_author_json),
    #    headers={"content-type": "application/json"},
    #)


    cookies = {"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")}
    response = await datasette.client.get("/-/datasette-book-collection/add-new-book", cookies=cookies)
    assert response.status_code == 200
    csrftoken = response.cookies["ds_csrftoken"]
    cookies["ds_csrftoken"] = csrftoken
    response = await datasette.client.post(
        "/-/datasette-book-collection/add-new-book",
        data={
            "isbn": "9781718503762",
            "title": "Machine Learning and AI Beyond the Basics",
            "author-name-1": "Sebastian Raschka",
            "author-openlibrary-id-1": "OL7246580A",
            "csrftoken": csrftoken,
            "formtype": "lookup",
            "add_new_copy": "false"
        },
        cookies=cookies,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_lookup_all_books(datasette):
    response = await datasette.client.get("/test/library.json")
    assert response.status_code == 200
    results = response.json()
    books = []
    for row in results['rows']:
        books.append(row['title'])
    assert 'Artificial Intelligence' in books
    assert 'Machine Learning and AI Beyond the Basics' in books

# this test looks up a book that we don't have in the local library 
# but that we do have a book by one of the authors so we should get back a book
# with a null book_id, and then in authors we should find an author_id for sebastian raschka
# but not for the other authors

@pytest.mark.asyncio
async def test_lookup_four_author_seb_book(datasette, httpx_mock):
    httpx_mock.add_response(
        url="https://openlibrary.org/isbn/9781801819312.json",
        json=json.loads(ml_with_pytorch_json),
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL7495021A.json",
        json=json.loads(hayden_liu_author_json),
        headers={"content-type": "application/json"},
    )

    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL7495683A.json",
        json=json.loads(vahid_mirjalili_author_json),
        headers={"content-type": "application/json"},
    )

    httpx_mock.add_response(
        url="https://openlibrary.org/authors/OL10269287A.json",
        json=json.loads(dmytro_dzhulgakov_author_json),
        headers={"content-type": "application/json"},
    )


    cookies = {"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")}
    response = await datasette.client.post("/-/datasette-book-collection/book-lookup", data={"isbn": "9781801819312"})
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    results = response.json()
    print(results)
    from_json = IsbnLookupResult.model_validate(results)
    assert from_json
    assert from_json.book.title == 'Machine Learning with Pytorch and Scikit-Learn'
    assert from_json.book.book_id == None
    assert len(from_json.authors) == 4
    assert (from_json.authors[0].name == 'Sebastian Raschka' and from_json.authors[0].author_id is not None) or \
              (from_json.authors[1].name == 'Sebastian Raschka' and from_json.authors[1].author_id is not None) or \
                (from_json.authors[2].name == 'Sebastian Raschka' and from_json.authors[2].author_id is not None) or \
                    (from_json.authors[3].name == 'Sebastian Raschka' and from_json.authors[3].author_id is not None)
    assert (from_json.authors[0].name == 'Vahid Mirjalili' and from_json.authors[0].author_id is None) or \
                (from_json.authors[1].name == 'Vahid Mirjalili' and from_json.authors[1].author_id is None) or \
                    (from_json.authors[2].name == 'Vahid Mirjalili' and from_json.authors[2].author_id is None) or \
                        (from_json.authors[3].name == 'Vahid Mirjalili' and from_json.authors[3].author_id is None)
