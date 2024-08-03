# Datasette-plugin-book-collection

A [Datasette](https://datasette.io) plugin to make it easy to create a SQLite database to inventory a book collection, with some UI helpers to scan barcodes and lookup metadata from OpenLibrary

**THIS CODE WILL CHANGE AND THE DATABASE SCHEMA WILL CHANGE AND MAY NOT HAVE AN EASY MIGRATION. BE CAUTIOUS IN HOW MUCH CATALOGING YOU DO WITH THIS FOR NOW IN CASE YOU HAVE TO REDO IT**

## Features
 * Scan book barcodes with phone camera
 * Lookup book by ISBN and fetch metadata from OpenLibrary
 * Fetch cover images from OpenLibrary and store them in your SQLite instance
 * Take a photo of your book and store that in your SQLite instance as well
 * All of the regular Datasette features such as serving a web interface to your book collection, including fulltext search of titles and faceting
 * Copies of books can have associated locations as a free-form text field, e.g. "shelf1" or "bedroom bookcase" or whatever. The web form for adding a new book automatically puts the last location used, to make it fast to scan an entire shelf without having to retype the location. 
 * With the [datasette-write-ui plug-in](https://datasette.io/plugins/datasette-write-ui) you can edit the book data after importing it. 
 * The 'load-isbn' command lets you specify an ISBN on the command line and the plug-in will search OpenLibrary for that ISBN and fetch the associated metadata and store it in the SQLite database as a copy of the book. 

I built this plugin because a couple of times over the years I've nearly bought a book I already own. 
I want a UI to be able to quickly go through my collection and record it, minimizing what I have to type in. 

I also want to own my own data and do not want to depend on a 3rd party service. In this sense, it's similar to what Simon Willison, the creator of Datasette, calls a [Personal Data Warehouse](https://simonwillison.net/2020/Nov/14/personal-data-warehouses/) or what Jon Udell would call [Lifebits](https://jonudell.net/tpc/). Datasette gives you a nice way to get to [file over app](https://stephango.com/file-over-app) so a plug-in for Datasette to do data collection felt like a good approach. 
Even if Simon abandons Datasette tomorrow, you'll have all of your book data in a SQLite file, which should be supported for at least the next several decades.  

<img src="scan-barcode.gif" alt="Using the barcode scanner on mobile" style="width: 100%; max-width: 400px;">

 ## Non-goals
 This is not meant to be a system for supporting a lending library, nor does it interface to services like GoodReads. 
 It's a book inventory, and not a reading log or a social app.

 This is only for book metadata and does not manage the content of any of the books, including any e-books. You can't search inside books. 

 Datasette does expect a certain level of technical skill from its users so this plugin might not be an appropriate book inventory system for many potential users. 
## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-plugin-book-collection
```

## Configuration 
In wherever you have configured your [Datasette Metadata](https://docs.datasette.io/en/stable/plugins.html#plugin-configuration) for plugins you can tell the book collection plugin which database it should use for its tables. 
For example, this could be your `metadata.json` file:

```json
{
  "plugins": {
    "datasette-plugin-book-collection": { "database" : "books"}
   }
}
```
## Usage
There is not yet an automatic database initialization. 
For now, you have to initialize the database with the built-in command before importing any books.

```bash
datasette initialize-book-tables --metadata=metadata.json books.db
```
Then start datasette as normal. 
To add a book, visit your datasette instance at `https://<YOUR.DATASETTE:PORT>/-/datasette-book-collection/add-new-book`

*Note: Browsers require that in order to use the javascript barcode scanner APIs, the app must be served using HTTPS. 
[Datasette can natively serve HTTPS](https://docs.datasette.io/en/stable/cli-reference.html#datasette-serve) with the -ssl-keyfile and -ssl-certfile options, or you could run Datasette behind a proxy that is configured to serve HTTPS*

To add a book, you must have the ['insert-row' permission](https://docs.datasette.io/en/stable/authentication.html) for that database.

## Known bugs and future plans
* Internally, processing the web form has been split up into several database statements and are not yet all packaged back up into a single database transaction, so there can be weird artifacts like authors without books or multiple copies of a book. 
* There is no indicator when web requests to OpenLibrary are in-progress. I'll add a spinner to give more indication that the computer is 'thinking'
* There is a SQL view created for the entire library that's accessible via the usual SQLite UI, but Datasette makes it really easy to create custom pages so I will make a nice "shelf" view with all of the cover images. 
* The test suite is very basic and not very complete
* The UI looks horrible because I am bad at CSS
* With the [write-ui plugin](https://datasette.io/plugins/datasette-write-ui) you can edit book data, but it might be nicer to support that directly via the plugin. 
* Updating and re-downloading book cover images needs a UI, since even with the write-ui plugin it would be very difficult to do. 
* The javascript libraries are currently pulled from a CDN and should instead be packaged with and served by the plugin-in. 
* The barcode detection code is called too frequently.
* There are a few internal APIs that might be useful. In fact, it might be worth thinking about abandoning the Datasette form version and expose all of the functionality via a JSON API.
* Convert the print calls into proper logging

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:
```bash
cd datasette-plugin-book-collection
python3 -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
pytest
```
## Dependencies and thank yous
Besides Datasette and Simon's closely-associated [Sqlite-utils](https://sqlite-utils.datasette.io/en/stable/index.html), the Python code uses [Pydantic](https://docs.pydantic.dev/latest/) and [Starlette](https://www.starlette.io/)

The UI code uses a bit of [Alpine.js](https://alpinejs.dev/). 
Because Safari on iOS does not support the browser Barcode Detection API, the plug-in uses the [barcode-detector-polyfill](https://github.com/undecaf/barcode-detector-polyfill) library, which in turn uses a WASM-compiled version of the ZBar Barcode Reader. Hopefully a future version of iOS will natively support the Barcode Detection API.

Having these libraries available made this project significantly easier, and thank you to the respective authors and contributors. 