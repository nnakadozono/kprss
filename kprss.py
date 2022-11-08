import os, sys
import datetime
import time
import pickle

import requests
from bs4 import BeautifulSoup

import sqlite3

import dropbox

from feedgen.feed import FeedGenerator
from pytz import timezone

kplong = os.environ['KPLONG']
kp = os.environ['KPSHORT']
rooturl = f'https://www.{kp}.com'
usr = os.environ['KPUSR']
psw = os.environ['KPPSW']

sqlite3db = os.environ['KPDB']

DBX_ACCESS_TOKEN = os.environ['KP_DBX_ACCESS_TOKEN']

rssfilename = os.environ['KPRSS']

def connect_db(sqlite3db):
    # Connect sqlite3
    # detect_types is for date
    conn = sqlite3.connect(sqlite3db, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = conn.cursor()

    # Create tables
    c.execute(f'''CREATE TABLE IF NOT EXISTS {kp}
                 (key text PRIMARY KEY, url text, date date, dayid integer, title text, article text, photo integer, chart integer, media text, category text)''')

    c.execute(f'''CREATE TABLE IF NOT EXISTS photo_chart
                 (key text PRIMARY KEY, fkey text REFERENCES {kp} (key), type text, i integer, url text, text text, filename text, url_dbx text)''')
    return conn

def load_cookies(session):
    with open('cookies.pkl', 'rb') as f:
        session.cookies = pickle.load(f)

def save_cookies(session):
    with open('cookies.pkl', 'wb') as f:
        pickle.dump(session.cookies, f)

def login():
    # Access
    s = requests.Session()
    s.headers['Accept-Language'] = 'ja'
    s.headers['User-Agent'] = 'Mozilla/5.0'
    #r = s.get(rooturl)

    # Login
    payload = {
        'mode': 'login',
        'tran': '',
        'ext_login': usr,
        'ext_passwd': psw   
    }
    r = s.post(rooturl+'/login/', data=payload)

    time.sleep(5)
    soup = BeautifulSoup(r.text, features="lxml")
    error = soup.find(class_='error_text')
    if (error is not None) and error.get_text().startswith('このアカウントは現在ご利用中です'):
        print("The number of login users exceeds its limitation. Try it again later.")
        sys.exit()
    else:
        save_cookies(s)

    return s, r

def get_todays_linklist(s):
    # Get and store contents ==========================    
    # Get links
    try:
        r = s.get(rooturl)
        soup = BeautifulSoup(r.text, features="lxml")

        articles = []
        # Pickup
        for pickup in soup.find_all(id='home_pickup'):
            link = rooturl + pickup.a.get('href')
            #print(link)
            articles.append(Article(link, category=''))
        # Usual
        for articles_list in soup.find_all(class_='articles_list'):
            for li in articles_list.find_all('li'):
                link = rooturl + li.find('a').get('href')
                #print(link)
                articles.append(Article(link, category=''))
    #except:
    except Exception as e:
        print(e)
        # Logout the page 
        r = s.get(rooturl + '/logout/')

    return articles

def get_articles(s, articles):
    # Get each page
    try:
        for artcl in articles:
            print(artcl.key)
            artcl.get_article(s)
            #print(artcl.title)
            time.sleep(1)
    except Exception as e:
        print(e)
        # Logout the page 
        r = s.get(rooturl + '/logout/')
    finally:
        # Logout the page 
        r = s.get(rooturl + '/logout/')

    return articles

def store_articles_to_db(articles, c, conn):
    for artcl in articles:
        # Check if data is already existed or not
        c.execute(f"SELECT * FROM {kp} WHERE key=?", (artcl.key,))
        if c.fetchone() == None:
            c.execute(f"INSERT INTO {kp} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", artcl.to_tuple())
    conn.commit()

def upload_photos(articles, dbx):
    photos = []
    for artcl in articles:
        for i in range(artcl.photo):
            pht = Photo(artcl, i)
            pht.upload_and_get_shared_link(dbx)
            os.remove(pht.filename)
            photos.append(pht)
    return photos

def store_photos_to_db(photos, c, conn):
    for pht in photos: 
        # Check if data is already existed or not
        c.execute("SELECT * FROM photo_chart WHERE key=?", (pht.key,))
        if c.fetchone() == None:
            print(pht.key)
            c.execute("INSERT INTO photo_chart VALUES (?, ?, ?, ?, ?, ?, ?, ?)", pht.to_tuple())
    conn.commit()

class Article():
    def __init__(self, link, category):
        self.link = link
        self.category = category

        self.media = kp
        self.date = ''
        self.dayid = link.split('/')[-2]
        self.key = link

        self.photo = 0
        self.photo_link = []
        self.photo_text = []
        self.chart = 0

    def get_article(self, session):
        '''Get each page, store in article'''
        r = session.get(self.link)
        self.soup = BeautifulSoup(r.text, features="lxml")

        self.category = self.soup.find(id='bread').find_all('li')[-1].get_text()
        self.title = self.soup.find(class_="article_title").get_text()
        if self.soup.find(class_="article_detail_text") is not None:
            self.article = self.soup.find(class_="article_detail_text").get_text().replace("\u3000", "")
        else:
            self.article = ""
        _date = self.soup.find(class_='date').get_text().split('日')[0]
        self.date = datetime.datetime.strptime(_date, '%Y年%m月%d').date()

        _photo = self.soup.find_all(class_='photo_set')
        if _photo is not None:
            self.photo = len(_photo)
            for p in _photo:
                if p.find(class_='cap') is not None:
                    t = p.find(class_='cap').get_text()
                else:
                    t = ""
                l = rooturl + p.img['src']
                self.photo_link.append(l)
                self.photo_text.append(t)
                self.get_photo(session, l)
        #print(self.tpl)

    def get_photo(self, session, link):
        '''Get photo'''
        r = session.get(link)
        fn = link.split('/')[-1]
        with open(fn, 'wb') as f:
            f.write(r.content)
        time.sleep(1)

    def to_tuple(self): 
        '''articles to articletuples (for DB)'''
        tpl = (self.key, self.link, self.date, self.dayid, self.title, self.article, self.photo, self.chart, self.media, self.category)
        return tpl

class Photo():
    def __init__(self, article, i):
        self.i = i
        self.link = article.photo_link[i]
        self.text = article.photo_text[i]
        self.type = "photo"

        self.filename = self.link.split('/')[-1]
        self.key = self.link
        self.fkey = article.key

    def upload_and_get_shared_link(self, dbx):
        '''Upload photo and get its shared link'''
        upload_to_dbx(dbx, self.filename)
        self.link_dbx = get_shared_link_dbx(dbx, self.filename)
        time.sleep(1)
        return self.link_dbx

    def to_tuple(self): 
        '''articles to articletuples (for DB)'''
        tpl = (self.key, self.fkey, self.type, self.i, self.link, self.text, self.filename, self.link_dbx)
        return tpl   

def create_rss(c, fname):
    # https://feedgen.kiesow.be/index.html
    fg = FeedGenerator()
    fg.id(rooturl)
    fg.title(kplong)
    fg.author( {'name':kp,'email':'xxx'} )
    fg.link( href=rooturl, rel='self' )
    fg.language('ja')
    fg.description(kplong)

    # Feed entry
    c.execute(f"SELECT * FROM {kp} WHERE date > date('now','-4 days')")
    articles_res = c.fetchall()
    for row in articles_res:
        #print(row)
        key, url, date, dayid, title, artic, photo, chart, media, category = row
        artic = '<h3>{0}</h3><br><b>{1}</b><br>'.format(title, category) + artic
        c.execute("SELECT * FROM photo_chart WHERE fkey=?", (key,))
        p_res = c.fetchall()
        for rphoto in p_res:
            _, _, _, _, _, ptext, _, plink= rphoto
            artic += '<br><img src="{0}" alt="{1}">'.format(plink, ptext)

        fe = fg.add_entry()
        fe.id(key)
        fe.title(title)
        fe.link(href=url)
        fe.content(artic.replace('\n', '<br>'))
        fe.published(datetime.datetime(date.year, date.month, date.day, tzinfo=timezone('Asia/Tokyo')))

    # Write the RSS feed to a file
    fg.rss_file(fname) 


def main():
    # Connect DB  =====================================
    conn = connect_db(sqlite3db)
    c = conn.cursor()

    # Connect DBX  ====================================
    dbx = dropbox.Dropbox(DBX_ACCESS_TOKEN)

    # Access Web and get articles  ====================
    s, r = login()
    articles = get_todays_linklist(s)
    #articles = articles[:3] ############################
    articles = get_articles(s, articles)

    # Store articles into database ==========
    store_articles_to_db(articles, c, conn)

    # Upload photos and charts. Store the information into photo_chart table
    photos = upload_photos(articles, dbx)
    store_photos_to_db(photos, c, conn)

    # RSS =============================================
    create_rss(c, rssfilename)

    # Move the RSS file to destination
    upload_to_dbx(dbx, rssfilename)
    get_shared_link_dbx(dbx, rssfilename)

    # Close =========================================    
    # We can also close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    conn.close()

    return articles


def upload_to_dbx(dbx, name, overwrite=True):
    """Upload a file.
    Return the request response, or None in case of error.
    """
    # This script was gotten from sample in official site
    #path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    path = '/%s' % (name)
    while '//' in path:
        path = path.replace('//', '/')
    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(name)
    with open(name, 'rb') as f:
        data = f.read()
    try:
        res = dbx.files_upload(
            data, path, mode,
            client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
            mute=True)
    except dropbox.exceptions.ApiError as err:
        print('*** API error', err)
        return None
    print('uploaded as', res.name.encode('utf8'))
    return res

def get_shared_link_dbx(dbx, filename):
    m = dbx.sharing_create_shared_link('/'+filename)
    return m.url.replace("dl=0", "raw=1")

if __name__ == '__main__':
    main()
