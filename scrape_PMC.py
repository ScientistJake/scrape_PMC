'''
scrape_PMC.py
By: Jake Warner 
On: Feb 2. 2018
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
	
	scrapes/extracts ids from an esearch query xml result
	'''
	if db is None:
		db = 'pmc'
	term = searchterm
	if maxretrieve is None :
		maxretrieve = 20
	retmax = str(maxretrieve)
	
	url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db='+db+'&term='+term+'&retmode=xml&retmax='+retmax
	response = urllib.request.urlopen(url).read()
	soup = BeautifulSoup(response, "lxml")
	
	idlist = []
	for id in soup.find_all("id"):
		idlist.append(id.contents)
	return(idlist)

####
#
# Using eutils, get metadata from the article entrez xml data:
#
####

def get_summary(id,db=None):
	'''
	get_summary:
	id = pmc id
	db = database to be searched. Only uses pmc for now
	returns a dictionary of article metadata (see end of function for fields)
	
	scrapes/extracts the xml from an efetch query xml result
	'''
	if db is None:
		db = 'pmc'
	retmode = "xml"
	id = str(id)
	url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db="+db+'&id='+id+'&retmode='+retmode
	response = urllib.request.urlopen(url).read()
	soup = BeautifulSoup(response, "lxml")

	title = soup.find("article-title").text
	
	names=[[],[]]
	for surname in soup.find('article-meta').find_all('surname'):
		names[0].append(surname.contents)
	for firstname in soup.find('article-meta').find_all('given-names'):
		names[1].append(firstname.contents)
	authors =[]
	for i in range(len(names[0])):
		authors.append(names[0][i][0]+', '+names[1][i][0])

	#old articles might not have abstract
	try:
		abstract = soup.find("abstract").text
	except:
		abstract = ''
	
	doi = soup.select('article-id[pub-id-type="doi"]')
	#some articles have no doi
	try:
		doi = doi[0].text
	except:
		doi = ''
	doi = str(doi)

	journal = soup.find("journal-title").text

	#some articles have no day
	try:
		pubday = soup.find("day").text
	except:
		pubday = ''
	try:
		pubmonth = soup.find("month").text
	except:
		pubmonth = ''
	pubyear = soup.find("year").text
	pubdate = pubday +'/'+ pubmonth+'/' + pubyear
	
	article_meta = {}
	article_meta['doi'] = doi
	article_meta['title'] = title
	article_meta['journal'] = journal
	article_meta['pubdate'] = pubdate
	article_meta['pubyear'] = pubyear
	article_meta['authors'] = authors
	article_meta['first_author'] = names[0][0][0]
	article_meta['last_author'] = names[0].pop()
	article_meta['abstract'] = abstract

	return(article_meta)

####
#
# Visit the pmc article, extract locations of the figures and pdf, capture the caption and figname
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
	article_contents = {}
	
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

	#grab the pdf link if it's there:
	pdflink=''
	for link in soup.find('div','format-menu').find_all('a'):
		if re.search('pdf',link['href']):
			pdflink=link['href']
			pdflink=ncbibase+pdflink

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
		#remove comments
		comments = linksoup.findAll(text=lambda text:isinstance(text, Comment))
		[comment.extract() for comment in comments]

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

	#load everything into the dictionary:
	article_contents['figname'] = figname
	article_contents['image'] = image
	article_contents['caption'] = caption
	article_contents['pdf'] = pdflink

	return(article_contents)

####
#
# Download the articles, pdfs and meta data:
#
####

def get_articles(searchterm,maxretrieve=None,quiet=None, justpdf=None, dump=None):
	'''
	get_articles
	searchterm = searchterm to use for esearch
	maxretrieve = number of articles to get
	quit = boolean, if true, supresses messages
	justpdf = boolean, if true does not output figures or metadata
	dump = boolean, if true does not create sub directories for each article
	'''

	#Add a header to our requests
	opener = urllib.request.build_opener()
	opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:55.0) Gecko/20100101 Firefox/55.0')]
	urllib.request.install_opener(opener)
	
	#parse the arguments:
	if maxretrieve is None :
		maxretrieve = 20
	if not quiet is None :
		quiet = True
	if not quiet:
		print('fetching articles. If your ID list is long consider downloading off hours...')
	if not justpdf is None :
		justpdf = True
	if not dump is None :
		dump = True
		
	#retrieve ids for the searchterm
	ids = get_pmc_ids(searchterm, maxretrieve)
	
	
	#Download article contents and pdf for each id
	for id in ids:
		#get metadata and summary
		summary = get_summary(id[0])
		article_prefix = summary['pubyear']+'_'+summary['first_author']
		#spaces have no place in these filenames
		article_prefix = re.sub(' ','_',article_prefix)
		
		#dump mode skips this since we're not making directories
		if not dump:
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
			print('Downloading: '+summary['first_author']+' et al. '+summary['pubyear'])
		article_contents = scrape_article(id[0])

		#this block gets the figures
		# it is skipped in pdf only mode
		if not justpdf:
			#loop the figures, sink them. sink a caption as well
			for i in range(len(article_contents['figname'])):
				filename = article_prefix +'/'+ article_contents['figname'][i]+'.jpg'
				#spaces have no place in these filenames
				filename = re.sub(' ','_',filename)
				if len(filename) > 100:
					filename = filename[0:99]
				imageurl = article_contents['image'][i]
				#this downloads the image:
				try:
					urllib.request.urlretrieve(imageurl, filename=filename)
				except:
					print('Make error report here')
				#write a caption file for each figure
				captionfile = article_prefix +'/'+ article_contents['figname'][i]+'_caption.txt'
				captionfile = re.sub(' ','_',captionfile)
				caption = article_contents['caption'][i]
				with open(captionfile, "w") as text_file:
					print(f"{caption}", file=text_file)

		#no metadata in PDF mode
		if not justpdf:		
			#print out the article metadata:
			summaryfile = article_prefix +'/'+article_prefix+'_meta.txt'
			with open(summaryfile, "w") as text_file:
				authorlist = ''
				#a little extra formatting for the author list
				for author in summary['authors']: 
					authorlist += author +'; '
				#write the metadata
				print(f"Title: {summary['title']}\ndoi: {summary['doi']}\nAuthors: {authorlist}\nPublication date: {summary['pubdate']}\nJournal: {summary['journal']}\n\n{summary['abstract']}", file=text_file)

		# dump mode runs the dir check above as .isfile before writing the pdf
		if dump:
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
		else:
			pdffile = article_prefix +'/'+article_prefix+'.pdf'

		try:
			urllib.request.urlretrieve(article_contents['pdf'], filename=pdffile)
		except:
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
parser.add_argument("--pdf_only", action="store_true", help="Download PDFs only, not figures")
parser.add_argument("--dump_mode", action="store_true", help="Don't create subfolders and output all files to current directory.")
parser.add_argument("--quiet", action="store_true", help="Suppress output messages.")
args = parser.parse_args()

#replace spaces in search term
searchterm = re.sub(" ", "+", args.searchterm)

#check for max articles:
if args.max_articles:
	maxretrieve = args.max_articles
else:
	maxretrieve = None

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

#dump mode can ONLY be used with pdf, otherwise its too hard to manage figure names:
if args.dump_mode and not args.pdf_only:
	print("Sorry... dump_mode is only for use with pdf_only")
	sys.exit()

#parse  the rest:
if args.dump_mode:
	dump = True
else:
	dump = None
if args.pdf_only:
	justpdf = True
else:
	justpdf = None
if  args.quiet:
	quiet = True
else:
	quiet = None

get_articles(searchterm,maxretrieve=maxretrieve,quiet=quiet, justpdf=justpdf, dump=dump)
