import xml.etree.ElementTree as ET

import urllib2

import re

def get_pmc_ids(searchterm, maxretrieve=None,db=None):
	'''
	get_pmc_ids:
	searchterm = a string containing the search term, no spaces.
	maxretrieve = integer indicating number of records to retrieve
	'''
	if db is None:
		db = 'pmc'
	term = searchterm
	if maxretrieve is None :
		maxretrieve = 20
	retmax = str(maxretrieve)
	
	url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db='+db+'&term='+term+'&retmode=xml&retmax='+retmax
	req = urllib2.Request(url)
	response = urllib2.urlopen(req).read()
	resXML = ET.fromstring(response)
	
	idlist = []	
	for id in resXML.findall(".//Id"):
		idlist.append(id.text)
	return(idlist)

def get_summary(id,db=None):
	
	if db is None:
		db = 'pmc'
	retmode = "xml"
	id = str(id)
	url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db="+db+'&id='+id+'&retmode='+retmode
	req = urllib2.Request(url)
	response = urllib2.urlopen(req).read()
	resXML = ET.fromstring(response)

	title = resXML.find(".//article-meta/title-group/article-title").text
	
	names=[[],[]]
	for surname in resXML.findall(".//article-meta/contrib-group/contrib/name/surname"):
		names[0].append(surname.text)
	for firstname in resXML.findall(".//article-meta/contrib-group/contrib/name/given-names"):
		names[1].append(firstname.text)
	authors =[]
	for i in xrange(len(names[0])):
		authors.append(names[0][i]+', '+names[1][i])

	abstractnodes = resXML.find(".//article-meta/abstract").iter()
	abstract = ''
	for section in abstractnodes:
		if section.tail:
			abstract += section.text + section.tail
		else:
			abstract += section.text

	doi = resXML.find(".//article-meta/article-id[@pub-id-type='doi']").text
	doi = str(doi)

	journal = resXML.find(".//journal-title").text

	pubday = resXML.find(".//pub-date/day").text
	pubmonth = resXML.find(".//pub-date/month").text
	pubyear = resXML.find(".//pub-date/year").text
	pubdate = pubday +'/'+ pubmonth+'/' + pubyear
	
	article_meta = {}
	article_meta['doi'] = doi
	article_meta['title'] = title
	article_meta['journal'] = journal
	article_meta['pubdate'] = pubdate
	article_meta['pubyear'] = pubyear
	article_meta['authors'] = authors
	article_meta['abstract'] = abstract

	return(article_meta)

def scrapeArticle: 
  
## go to url of pmc full article for the given pmcid
id = str(id)
ncbiurlbase = "https://www.ncbi.nlm.nih.gov/pmc/articles/"
articleurl = ncbiurlbase + id

user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
headers={'User-Agent':user_agent,} 
req = urllib2.Request(articleurl, headers=headers)

response = urllib2.urlopen(req)
if response.code != 200:
	raise Exception("Failed to access ncbi: Bad URL?")

page = response.read()

from bs4 import BeautifulSoup
soup = BeautifulSoup(page)

links = []
for elem in soup.select('a[class="figpopup"]'):
	links.append(elem['href'])

figurlbase = "https://www.ncbi.nlm.nih.gov"
name = []
image = []
caption = []
for figlink in links:
	figurl = figurlbase + figlink.encode("utf-8")
	get = urllib2.Request(figurl, headers=headers)
	res = urllib2.urlopen(get)
	linkpage = res.read()
	linksoup = BeautifulSoup(linkpage)

	for elem in linksoup.find_all('div','figure'):
		try:
			name.append(elem.previous_sibling.contents)
		except:
			name.append(elem.previous_sibling)
		
	#get image link
	for elem in linksoup.select('.tileshop, .fig-image'):
		image.append(elem['src'])

for elem in linksoup.find_all('div','caption'):
	print elem.children.contents





