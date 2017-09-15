## CNN Transcripts 

CNN provides transcripts for its shows at [http://edition.cnn.com/TRANSCRIPTS/](http://edition.cnn.com/TRANSCRIPTS/). 

The transcripts are available for shows starting `1999/10/01`. See [http://edition.cnn.com/TRANSCRIPTS/1999.10.01.html](http://edition.cnn.com/TRANSCRIPTS/1999.10.01.html). However, we get a 'Page not found' error when we follow links until `1999/12/31`. So we started scraping the data from `2000/01/01`.

CNN went through a few HTML styles of the news transcripts between `2000/01/01`and 2014. So there are two scapers to parse the different HTML styles:

* [till 2002/9/17](scripts/cnn-1.py)
* [from 2002/9/17](scripts/cnn-1.py)

### Data

The parsed data are posted at [http://dx.doi.org/10.7910/DVN/ISDPJU](http://dx.doi.org/10.7910/DVN/ISDPJU). For copyright reasons, access is restricted for research purposes only. The data are split into 6 files:

* `cnn-1.csv`. Data from 2000/01/01--2000/04/20. No. of transcripts = 7017
* `cnn-2.csv`. Data from  2000/04/21--2001/04/03. No. of transcripts = 21381
* `cnn-3.csv`. Data from  2001/04/04--2002/08/06. No. of transcripts = 35269
* `cnn-4.csv`. Data from  2002/08/07--2002/09/16. No. of transcripts = 2343
* `cnn-5.csv`. Data from  2002/09/17--2012/05/18. No. of transcripts = 101336
* `cnn-6.csv`. Data from  2012/05/19--2014/06/17. No. of transcripts = 23536

Total number of transcripts: 190,882


### Notes

* 2000-04-21 New format error
* 2000-04-22 content within <p> and </p> tag
* 2001-04-04 No URL prefix, subheader ==> h4, content next table <br> tag
* Scripts from 2014
