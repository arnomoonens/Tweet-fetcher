# Tweet-fetcher
Python script that fetches tweets based on a search term and puts them into a MongoDB database

## Requirements
* [Twython](https://github.com/ryanmcgrath/twython)
* [Pymongo](https://api.mongodb.org/python/current/)
* A running [MongoDB](https://www.mongodb.org/) database
* A `config.py` files (see `config.py.example` and the list beneath)

## Configuration
* The `collect_sources` list contains tuples of respectively the term for which to search with the _Twitter API_ and the destination collection in the _MongoDB_ database.
* The Twitter configuration settings in `config.py` can be obtained by registering your own application [here](https://apps.twitter.com/).
* The `BOXCAR_KEY` is used to push a notification to your device after the script is done collecting. The key can be obtained by logging in to [Boxcar](https://boxcar.io/client), going to the Settings page and copying the _Access Token_.
