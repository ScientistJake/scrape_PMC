# Pumedcentral image scraper
# By: Jake Warner
# On: Feb 2, 2018
# Inspired by the pmc sqlite scraper here: https://github.com/frangipane/scrape_pubmedcentral
# Some of the functions in the above are broken though =(
# The functions below work (for now) and are database free  


library("RCurl")
library("XML")
library("httr")
library("rvest")
library("stringr")

getPMCIds <- function(searchterm,database="pmc",maxretrieve=20){
  urlbase <- "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
  query <- paste0(urlbase,"db=",database,"&term=",searchterm,"&retmode=xml&retmax=",maxretrieve)
  response = getURL(query)
  response.xml = xmlParse(response)
  uids = getNodeSet(response.xml,"//Id") %>% sapply(.,xmlValue)
  return(uids)
}

getSummary <- function(id, database="pmc"){
  
  urlbase = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
  efetch = "efetch.fcgi?"
  db = paste0("db=",database)
  retmode = "retmode=xml"
  
  #build up the url with the options
  url.efetch = paste0(urlbase, efetch, db, "&", "id=", id, "&", retmode)
  
  response.efetch = getURL(url.efetch)
  reponse.xml = xmlParse(response.efetch)
  
  title = getNodeSet(reponse.xml,"//article-meta/title-group/article-title") %>% sapply(.,xmlValue)
  
  authors.surname = getNodeSet(reponse.xml,"//article-meta/contrib-group/contrib/name/surname") %>% sapply(.,xmlValue)
  authors.firstname = getNodeSet(reponse.xml,"//article-meta/contrib-group/contrib/name/given-names") %>% sapply(.,xmlValue)
  authors = paste(authors.surname, authors.firstname, sep=",")
  
  #combine authorlist
  authors = paste(authors, collapse="; ")
  
  abstract = getNodeSet(reponse.xml,"//article-meta/abstract") %>% sapply(.,xmlValue)
  doi= getNodeSet(reponse.xml,"//article-meta/article-id[@pub-id-type='doi']") %>% sapply(.,xmlValue)
  
  ## some articles lack a doi
  if (length(doi)==0) doi = ""
  
  journal = getNodeSet(reponse.xml,"//journal-title") %>% sapply(.,xmlValue)

  pubdate.day = getNodeSet(reponse.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/day") %>% sapply(.,xmlValue)
  pubdate.month = getNodeSet(reponse.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/month") %>% sapply(.,xmlValue)
  pubdate.year = getNodeSet(reponse.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/year") %>% sapply(.,xmlValue)
  pubdate = paste(pubdate.day,pubdate.month,pubdate.year, sep="/")

  article_meta = list(doi=doi, title=title, journal=journal, pubdate=pubdate,
                      authors=authors, abstract=abstract)
  return(article_meta)
}

scrapeArticle = function(id) {
  
  #visit pmc for the article, pass the response to getFigures
  ncbiurl = "https://www.ncbi.nlm.nih.gov/pmc/articles/"
  articleurl = paste0(ncbiurl, id)
  response <- GET(articleurl)
  
  # check the status to see if the url is ok
  if(!identical(status_code(response), 200L)) {
    stop('sorry, bad url')
    return(0)
  }
  
  article = content(response)
  
  #call getFigures and extract the names, links, and captions
  figures = getFigures(article)
  fig.names = figures$fig.names
  fig.links = figures$fig.links
  fig.captions = figures$fig.captions
  
  #load all the figure data into a df
  figDataframe = data.frame(
    Name = fig.names,
    URL = fig.links,
    Caption = fig.captions,
    stringsAsFactors = F)
  
  return(figDataframe)
}

getFigures = function(article) {
  ncbiBase = "https://www.ncbi.nlm.nih.gov"
  
  link = getNodeSet(htmlParse(article),"//a[contains(@class,'figpop') and contains(@target,'fig')]/@href") %>% sapply(., "[[", 1)
  link = unique(link)
  urlFigPage = paste0(ncbiBase, link)
  figPage = htmlParse(getURL(urlFigPage))
  
  fig.names = getNodeSet(figPage,"//div[@class='figure']/preceding::*[1]") %>% sapply(., xmlValue)
  fig.links = getNodeSet(figPage,"//img[@class='tileshop' or @class='fig-image']/@src")%>% sapply(., "[[", 1)
  fig.links = paste0(ncbiBase,fig.links)
  fig.captions = getNodeSet(figPage,"//div[@class='caption']") %>% sapply(., xmlValue)
  
  return(list(fig.names=fig.names, fig.links = fig.links, fig.captions = fig.captions))
}


downloadArticles = function(searchterm, database='pmc', max_results=20){
  ids <- getPMCIds(searchterm,database,max_results)
  
  for (id in ids){
    #get the summary
    summary <- getSummary(id,database)
  
    #make the directory
    dirname <- paste0(unlist(strsplit(summary$authors,split=','))[1],"_",unlist(strsplit(summary$pubdate,split='/'))[3])
    dirname <- gsub(" ","_",dirname)
    #check if the dirnam exists:
    if(dir.exists(dirname)){
      files <- list.files()
      #odd way to count but it works
      exist_number <- length(which(str_detect(files,dirname)))
      new_dirname <- paste0(dirname,"_",exist_number+1)
      dir.create(new_dirname)
    } else{
      dir.create(dirname)
    }
    
    metafilename <- paste0(dirname,"/",dirname,".meta.txt")
    sink(metafilename)
    print(summary)
    sink()
  
    figures <- scrapeArticle(id)
  
    #download figures
    for (figure in 1:length(figures$Name)){
      name <- figures$Name[figure]
      link <- figures$URL[figure]
      caption <- figures$Caption[figure]
      name <- gsub(" ","_",name)
      system(paste0("curl ",link," > ",dirname,"/",name,".jpg"))
    
      sink(paste0(dirname,"/",name,".caption.txt"))
      print(caption)
      sink()
    }
  }
}


