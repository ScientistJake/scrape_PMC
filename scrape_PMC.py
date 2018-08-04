'''
scrape_PMC.py
By: Jake Warner 
On: Aug 2. 2018
Python3
Report bugs or issues here: https://github.com/ScientistJake/scrape_PMC/issues
'''
from bs4 import BeautifulSoup, Comment
import argparse
import urllib
import urllib.request
import re
import os
import sys
import random
from urllib.request import Request, urlopen

####
#
# Using eutils, get the ids matching the search term
#
####
def get_pmc_ids(searchterm, maxretrieve=None,db=None):
	'''
	get_pmc_ids:
	searchterm = a string containing the search term, no spaces.
	maxretrieve = integer indicating number of records to retrieve
	db = database to be searched. Only uses pmc for now
	returns a list of ids
	extracts ids from an esearch query xml result
	'''
	if db is None:
		db = 'pmc'
	if maxretrieve is None :
		maxretrieve = 20
	retmax = str(maxretrieve)	
	url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db='+db+'&term='+searchterm+'&retmode=xml&retmax='+retmax+'&usehistory=y'
	response = urllib.request.urlopen(url).read()
	soup = BeautifulSoup(response, "lxml")
	results = {}
	results['webenv'] = soup.find("webenv").contents
	results['querykey'] = soup.find("querykey").contents
	idlist = []
	for id in soup.find_all("id"):
		idlist.append(id.contents)
	results['idlist'] = idlist
	return(results)

####
#
# program to get article summary and figures for a list
#
####
def get_article_contents(webenv, querykey, maxretrieve=None,db=None,quiet=None):
	
	ncbibase = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC"
	
	opener = urllib.request.build_opener()
	opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:55.0) Gecko/20100101 Firefox/55.0')]
	urllib.request.install_opener(opener)

	if maxretrieve is None :
		maxretrieve = 20
	if db is None:
		db = 'pmc'

	if not quiet is None :
		quiet = True

	# retrieve the search
	url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db="+db+"&retmode=xml&WebEnv="+webenv+"&query_key="+querykey+"&retmax="+str(maxretrieve)
	response = urllib.request.urlopen(url).read()
	soup = BeautifulSoup(response, "lxml")
	articles = soup.find_all('article')
	
	#here's where we put the results
	articles_scraped = []
	
	#ok go:
	for article in articles:
		
		summary = get_article_summary(article)
		
		pmc_id = summary['pmc_id']
		
		figures = scrape_article(pmc_id)
		
		pdf_link = get_pdf(pmc_id,quiet=quiet)
		
		if not quiet:
			print("fetching "+summary['first_author']+" et al. "+str(summary['pubyear'])+" PMC id:" +str(pmc_id))
	
		#attempt to find a url
		#try:
		#	pdf_link = get_pdf(str(pmc_id))
		#except:
		#	if not quiet:
		#		print("Couldn't locate PDF for PMC id:"+str(pmc_id))
		
		#load up the dictionary for this article
		article_contents = {}
		article_contents['doi'] = summary['doi']
		article_contents['pmc_id'] = summary['pmc_id']
		article_contents['title'] = summary['title']
		article_contents['journal'] = summary['journal']
		article_contents['pubdate'] = summary['pubdate']
		article_contents['pubyear'] = summary['pubyear']
		article_contents['authors'] = summary['authors']
		article_contents['first_author'] = summary['first_author']
		article_contents['last_author'] = summary['last_author']
		article_contents['abstract'] = summary['abstract']
		article_contents['fignames'] = figures['figname']
		article_contents['captions'] = figures['caption']
		article_contents['images'] = figures['image']
		article_contents['pdf_link'] = pdf_link
					
		#output it to the article list
		articles_scraped.append(article_contents)
	return(articles_scraped)

####
#
# article summary extractor/helper
#
####
def get_article_summary(article):
	#article is an xml record for one <article> tag
	
	#put it here:
	article_summary = {}
		
	#first get the identifying infos:
	article_summary['pmc_id'] = article.select('article-id[pub-id-type="pmc"]')[0].text

	#get doi
	doi = article.select('article-id[pub-id-type="doi"]')
	#some articles have no doi
	try:
		doi = doi[0].text
	except:
		doi = ''
	article_summary['doi'] = str(doi)
	
	article_summary['journal'] = article.find("journal-title").text
	
	article_summary['title'] = article.find("article-title").text
	names=[[],[]]
	for surname in article.find('article-meta').find_all('surname'):
		names[0].append(surname.contents)
	for firstname in article.find('article-meta').find_all('given-names'):
		names[1].append(firstname.contents)
	authors =[]
	for i in range(len(names[0])):
		authors.append(names[0][i][0]+', '+names[1][i][0])	
	first_author = names[0][0][0]
	last_author = names[0].pop()
	
	article_summary['authors'] = authors
	article_summary['first_author'] = first_author
	article_summary['last_author'] = last_author
		
	#get abstract
	#old articles might not have abstract
	try:
		abstract = article.find("abstract").text
	except:
		abstract = ''
	
	article_summary['abstract'] = abstract
	#some articles have no day
	try:
		pubday = article.find("day").text
	except:
		pubday = ''
	try:
		pubmonth = article.find("month").text
	except:
		pubmonth = ''
	pubyear = article.find("year").text
	article_summary['pubyear'] = pubyear
	article_summary['pubdate'] = pubday +'/'+ pubmonth+'/' + pubyear
	
	return(article_summary)

####
#
# figure scraper (Pubmedcentral)
#
####
def scrape_article(id): 
	'''
	scrape_article:
	id = pubmed central id
	returns a dictionary with figure, pdf locations; caption and figure names
	
	scrapes the pmc article site
	'''
	#this is where we store the results
	article_figures = {}
	
	## go to url of pmc full article for the given pmcid
	id = str(id)
	ncbibase = "https://www.ncbi.nlm.nih.gov"
	ncbiarticlebase = "https://www.ncbi.nlm.nih.gov/pmc/articles/"
	articleurl = ncbiarticlebase + id
	#need to fake pmc to let us in
	user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
	headers={'User-Agent':user_agent,} 
	req = urllib.request.Request(articleurl, headers=headers)
	try:
		response = urllib.request.urlopen(req)
	except:
		print("Failed to access ncbi: Bad URL?")
		return
	
	#make sure the response is ok:
	if response.code != 200:
		raise Exception("Failed to access ncbi: Bad URL?")

	#parse the page
	page = response.read()
	soup = BeautifulSoup(page, "lxml")

	#find all the image links. They're in class figpopup:
	links = []
	for elem in soup.select('a[class="figpopup"]'):
		links.append(elem['href'])

	#loop through links and get the name, link and caption
	figname = []
	image = []
	caption = []
	for figlink in links:
		figurl = ncbibase + figlink
		figrequest = urllib.request.Request(figurl, headers=headers)
		figresponse = urllib.request.urlopen(figrequest)
		linkpage = figresponse.read()
		linksoup = BeautifulSoup(linkpage, "lxml")
		#remove the comments so it doesnt confuse the scrape
		for element in linksoup(text=lambda text: isinstance(text, Comment)):
			element.extract()

		#each of these is in a loop because there can be more than one figure on a page.
	
		#the figure name is just before the figure div, use previous.sibling
		for elem in linksoup.find_all('div','figure'):
			try:
				figname.append(elem.previous_sibling.text)
			except:
				figname.append(elem.previous_sibling)
		
		#get image link, it's in either tileshop or fig-image
		for elem in linksoup.select('.tileshop, .fig-image'):
			imagelink = elem['src']
			imagelink = ncbibase + imagelink
			image.append(imagelink)

		#get the caption(s)
		for elem in linksoup.find_all('div','caption'):
			caption.append(elem.text)
		
		#top up the caption?
		#sometimes there's one caption for two images. This just repeats the caption.
		while len(caption) < len(figname):
			caption.append(caption[-1])
	
	#check the figure names:
	#sometimes the scrape will catch a weird name if there's more than 1 image to a figure
	#this will add a name
	goodname = 'figX'
	j = 2
	for i in range(len(figname)):
		if re.search('fig',figname[i], re.IGNORECASE):
			goodname = figname[i]
			j= 2
		else:
			figname[i] = goodname + "." + str(j)
			j += 1
	
	#load everything into the dictionary:
	article_figures['figname'] = figname
	article_figures['image'] = image
	article_figures['caption'] = caption

	return(article_figures)

####
#
# figure scraper (XML records)
#
####
def get_figures_from_xml(article):
	#article is an xml pmc report
	#loop over the figures
	#extract captions
	#get figure names and image links
	fignames = []
	captions = []
	images = []
	for fig in article.find_all("fig"):
		try:
			figname = fig.find('label').text
		except:
			figname = 'untitled figure'
		fignames.append(figname)
		try:
			captions.append(fig.find('caption').text)
		except:
			captions.append("No Caption")
		graphics = fig.select('graphic')
	
		#there can be multiple images per figure
		for elem in graphics:
			imagelink = elem['xlink:href']
			imagelink = ncbibase + pmc_id + "/bin/"+imagelink +".jpg"
			images.append(imagelink)
		
		#this chunk helps name the image parts lik fig1.2 fig1.3 etc.
		#also duplicates the caption so the indexes line up
		if len(graphics) > 1:
			j = 2
			fig_part = fignames[-1]
			for i in range(len(graphics)-1):
				fignames.append(fig_part+"."+str(j))
				captions.append(captions[-1])
				j += 1

def get_pdf(pmc_id,quiet=None):
	if not quiet is None :
		quiet = True
	#attempt to find a url
	try:
		pdf_url = 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC'+str(pmc_id)+'/pdf/'
		req = Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
		pdf_link = urlopen(req).url
	except:
		pdf_link = ""
		if not quiet:
			print("Couldn't locate PDF for PMC id:"+str(pmc_id))
	return(pdf_link)

####
#
# Download/ writing program
#
####	
def download_articles(searchterm,maxretrieve=None,quiet=None, db=None):
	#parse the arguments:
	if maxretrieve is None :
		maxretrieve = 20
	if not quiet is None :
		quiet = True
	if not quiet:
		print('fetching articles. If your ID list is long consider downloading off hours...')
	if db is None:
		db = 'pmc'
	
	id_list = get_pmc_ids(searchterm, maxretrieve=maxretrieve,db=db)
	
	webenv = id_list['webenv'][0]
	querykey = id_list['querykey'][0]
	
	article_contents = get_article_contents(webenv, querykey, maxretrieve=maxretrieve,db=db,quiet=quiet)
	
	for record in article_contents:
		article_prefix = record['pubyear']+'_'+record['first_author']
		#spaces have no place in these filenames
		article_prefix = re.sub(' ','_',article_prefix)
		
		#check to make sure the directory doesn't exist.
		#if it does, count the directories and make a new dir with number of directories +1
		if os.path.isdir(article_prefix):
			counter=0
			for dir in os.listdir():
				if re.search(article_prefix,dir):
					counter += 1
			article_prefix = article_prefix +'_'+str(counter)
			os.makedirs(article_prefix)
		else:
			os.makedirs(article_prefix)
		
		#get figures
		if not quiet:
			print('Downloading: '+record['first_author']+' et al. '+record['pubyear']+' PMCID:'+record['pmc_id'])
		
		#this block gets the figures
		# it is skipped in pdf only mode

		#loop the figures, sink them. sink a caption as well
		for i in range(len(record['fignames'])):
			filename = article_prefix +'/'+ record['fignames'][i]+'.jpg'
			#spaces have no place in these filenames
			filename = re.sub(' ','_',filename)
			if len(filename) > 100:
				filename = filename[0:99]
			imageurl = record['images'][i]
			#this downloads the image:
			try:
				urllib.request.urlretrieve(imageurl, filename=filename)
			except:
				print('Make error report here')
			#write a caption file for each figure
			captionfile = article_prefix +'/'+ record['fignames'][i]+'_caption.txt'
			captionfile = re.sub(' ','_',captionfile)
			caption = record['captions'][i]
			with open(captionfile, "w") as text_file:
				print(f"{caption}", file=text_file)


		#print out the article metadata:
		summaryfile = article_prefix +'/'+article_prefix+'_meta.txt'
		with open(summaryfile, "w") as text_file:
			authorlist = ''
			#a little extra formatting for the author list
			for author in record['authors']: 
				authorlist += author +'; '
			#write the metadata
			print(f"Title: {record['title']}\ndoi: {record['doi']}\nAuthors: {authorlist}\nPublication date: {record['pubdate']}\nJournal: {record['journal']}\n\n{record['abstract']}", file=text_file)

		pdffile = article_prefix +'/'+article_prefix+'.pdf'

		try:
			urllib.request.urlretrieve(record['pdf_link'], filename=pdffile)
		except:
			if not quiet:
				print("Couldn't locate pdf")
####
#
# PDF only program
#
####
def pdf_dump(searchterm,maxretrieve=None,quiet=None, db=None):
	#parse the arguments:
	if maxretrieve is None :
		maxretrieve = 20
	if not quiet is None :
		quiet = True
	if db is None:
		db = 'pmc'

	id_list = get_pmc_ids(searchterm, maxretrieve=maxretrieve,db=db)
	
	webenv = id_list['webenv'][0]
	querykey = id_list['querykey'][0]

	ncbibase = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC"
	
	opener = urllib.request.build_opener()
	opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:55.0) Gecko/20100101 Firefox/55.0')]
	urllib.request.install_opener(opener)

	# retrieve the search
	url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db="+db+"&retmode=xml&WebEnv="+webenv+"&query_key="+querykey+"&retmax="+str(maxretrieve)
	response = urllib.request.urlopen(url).read()
	soup = BeautifulSoup(response, "lxml")
	articles = soup.find_all('article')
	
	for article in articles:
		
		summary = get_article_summary(article)
		
		pmc_id = summary['pmc_id']
				
		pdf_link = get_pdf(pmc_id,quiet=quiet)
		
		if not quiet:
			print("Downloading PDF: "+summary['first_author']+" et al. "+str(summary['pubyear'])+" PMC id:" +str(pmc_id))

		article_prefix = summary['pubyear']+'_'+summary['first_author']
		#spaces have no place in these filenames
		article_prefix = re.sub(' ','_',article_prefix)

		# dump mode runs the dir check above as .isfile before writing the pdf
		#check if the pdf exists
		#if file does exists add the count:
		if os.path.isfile(article_prefix+".pdf"):
			counter=0
			for dir in os.listdir():
				if re.search(article_prefix,dir):
					counter += 1
			article_prefix = article_prefix +'_'+str(counter)
		pdffile = './'+article_prefix+'.pdf'
		#print out the pdf:

		try:
			urllib.request.urlretrieve(pdf_link, filename=pdffile)
		except:
			if not quiet:
				print("Couldn't locate pdf")
		

####
#
# Main Program
#
####

#set up the arguments
parser = argparse.ArgumentParser(description="Download article figures, pdfs and metadata for a given search from PubMed Central")
parser.add_argument("searchterm", help="String used to search pmc.\nTest search terms at: 'https://www.ncbi.nlm.nih.gov/pmc/' To construct complex searches see: http://", type=str)
parser.add_argument("--max_articles", help="Max number of articles to retrieve", type = int)
parser.add_argument("--min_date", help="Minimum search date limit. Format: YYYY/MM/DD", type = str)
parser.add_argument("--max_date", help="Maximum search date limit. Format: YYYY/MM/DD", type = str)
parser.add_argument("--ids_only", action="store_true", help="Print IDs matching searchterm and quit.")
parser.add_argument("--pdf_dump", action="store_true", help="Download PDFs only, not figures")
parser.add_argument("--quiet", action="store_true", help="Suppress output messages.")
args = parser.parse_args()

#replace spaces in search term
searchterm = re.sub(" ", "+", args.searchterm)

#check for max articles:
if args.max_articles:
	maxretrieve = args.max_articles
else:
	maxretrieve = None

#shhh?
if  args.quiet:
	quiet = True
else:
	quiet = None

#check for mutual dependency of max and min date:
if args.min_date and not args.max_date:
	print("Please specify --max_date when using --min_date.")
	sys.exit()
if args.max_date and not args.min_date:
	print("Please specify --min_date when using --max_date.")
	sys.exit()
	
#get min and maxdate:
if args.max_date and args.min_date:
	searchterm += "&mindate="+args.min_date+"&maxdate="+args.max_date+"&datetype=pdat"

#ids only program:	
if args.ids_only:
	ids= get_pmc_ids(searchterm, maxretrieve=maxretrieve,db=None)
	for id in ids:
		print(id[0])
	sys.exit()

#pdf dump program:
if args.pdf_dump:
	pdf_dump(searchterm,maxretrieve=maxretrieve,quiet=quiet)
	sys.exit()

download_articles(searchterm,maxretrieve=maxretrieve,quiet=quiet)