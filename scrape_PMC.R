#pumed image scraper
library("RCurl")
library("XML")
library("httr")
library("rvest")
library("stringr")

getPMCIds <- function(searchterm,database,maxretrieve){
  urlbase <- "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
  query <- paste0(urlbase,"db=",database,"&term=",searchterm,"&retmode=xml&retmax=",maxretrieve)
  response = getURL(query)
  response.xml = xmlParse(response)
  uids = getNodeSet(response.xml,"//Id") %>% sapply(.,xmlValue)
  return(uids)
}

getSummary <- function(id, database="pmc"){
  
  url.base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
  ## eFetch utility
  efetch = "efetch.fcgi?"
  ## database to search
  db = paste0("db=",database)
  ## retrieval mode: data format of record to be returned
  retmode = "retmode=xml"
  
  ## compose url for eFetch
  url.efetch = paste0(url.base, efetch, db, "&", "id=", id, "&", retmode)
  
  data.efetch = getURL(url.efetch)
  data.xml = xmlParse(data.efetch)
  
  title = getNodeSet(data.xml,"//article-meta/title-group/article-title") %>% sapply(.,xmlValue)
  
  authors.surname = getNodeSet(data.xml,"//article-meta/contrib-group/contrib/name/surname") %>% sapply(.,xmlValue)
  authors.firstname = getNodeSet(data.xml,"//article-meta/contrib-group/contrib/name/given-names") %>% sapply(.,xmlValue)
  authors = paste(authors.surname, authors.firstname, sep=",")
  
  ## combine authors vector into one single string
  authors = paste(authors, collapse="; ")
  
  abstract = getNodeSet(data.xml,"//article-meta/abstract") %>% sapply(.,xmlValue)
  doi= getNodeSet(data.xml,"//article-meta/article-id[@pub-id-type='doi']") %>% sapply(.,xmlValue)
  
  ## some articles lack a doi
  if (length(doi)==0) doi = ""
  
  journal = getNodeSet(data.xml,"//journal-title") %>% sapply(.,xmlValue)

  pubdate.day = getNodeSet(data.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/day") %>% sapply(.,xmlValue)
  pubdate.month = getNodeSet(data.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/month") %>% sapply(.,xmlValue)
  pubdate.year = getNodeSet(data.xml,"//pub-date[@pub-type='epub' or @date-type='pub']/year") %>% sapply(.,xmlValue)
  pubdate = paste(pubdate.day,pubdate.month,pubdate.year, sep="/")

  article_meta = list(doi=doi, title=title, journal=journal, pubdate=pubdate,
                      authors=authors, abstract=abstract)
  return(article_meta)
}

scrapeArticle = function(id) {
  
  ## go to url of pmc full article for the given pmcid
  ncbiurl.base = "https://www.ncbi.nlm.nih.gov/pmc/articles/"
  url.article = paste0(ncbiurl.base, id)
  response <- GET(url.article)
  
  ## check if url is valid
  if(!identical(status_code(response), 200L)) {
    stop('sorry, bad url')
    return(0)
  }
  
  article = content(response)
  
  ## get urls and names of all popup figures in article
  figures = getFigures(article)
  fig.names = figures$fig.names
  fig.links = figures$fig.links
  fig.captions = figures$fig.captions
  
  ## create dataframe to hold metadata of figures matching search terms
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

ids <- getPMCIds("nematostella","pmc",20)
summary <- getSummary("5762905", database="pmc")
out <- scrapeArticle("5762905")

scrapey_scrape = function(searchterm, database, max_results, build_dir_tree){
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
      exist_number <- length(which(str_detect(files,"test")))
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


