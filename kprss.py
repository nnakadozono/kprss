import os, sys
import datetime
import time

import requests
from bs4 import BeautifulSoup

import sqlite3

import dropbox

from feedgen.feed import FeedGenerator
from pytz import timezone

import boto3
import zipfile


def _load_ssm_parameters(names, prefix=None):
    """Return dict of {name: value} for given parameter names.
    prefix: optional path prefix, no trailing slash required.
    """
    _ssm = boto3.client('ssm')
    if prefix:
        base = prefix.rstrip('/') + '/'
        keys = [base + n for n in names]
    else:
        keys = names

    resp = _ssm.get_parameters(Names=keys, WithDecryption=True)
    out = {}
    for p in resp.get('Parameters', []):
        name = p['Name']
        key = name.split('/')[-1] if prefix else name
        out[key] = p['Value']
    return out

SSM_PREFIX = os.environ.get('KP_SSM_PREFIX') 

_param_names = ['KPLONG','KPSHORT','KPUSR','KPPSW','KPDB',
                'KP_DBX_ACCESS_TOKEN','KPRSS','KP_S3_BUCKET']

try:
    _params = _load_ssm_parameters(_param_names, prefix=SSM_PREFIX)
except Exception as e:
    # Non-fatal: fall back to env and print warning (Lambda role may not have permissions)
    print("Warning: SSM parameter fetch failed - falling back to env vars:", e)
    _params = {}

def _cfg(name):
    return _params.get(name) or os.environ.get(name)

KPLONG = _cfg('KPLONG')  # Name used in RSS title and description
KP = _cfg('KPSHORT')     # URL, media short name and DB table name
ROOT_URL = f'https://www.{KP}.com'
USR = _cfg('KPUSR')
PSW = _cfg('KPPSW')

DB_FILE = _cfg('KPDB')   # database file name

DBX_ACCESS_TOKEN = _cfg('KP_DBX_ACCESS_TOKEN')

RSS_FILE_NAME = _cfg('KPRSS')

# COOKIE_FILE = os.environ.get('COOKIE_FILE', '/tmp/cookies.pkl')
S3_BUCKET = _cfg('KP_S3_BUCKET')
S3_DB_KEY = f"{DB_FILE}.zip"


def s3_download_db(local_path):
    if (not S3_BUCKET):
        print("S3_BUCKET is not set; skipping DB download.")
        return local_path
    s3 = boto3.client('s3')
    try:
        s3.download_file(S3_BUCKET, S3_DB_KEY, local_path)
        print(f"Downloaded DB from s3://{S3_BUCKET}/{S3_DB_KEY} to {local_path}")
    except Exception as e:
        print(f"S3 download failed")
        raise


def s3_upload_db(local_path):
    if not S3_BUCKET:
        print("S3_BUCKET is not set; skipping DB upload.")
        return
    s3 = boto3.client('s3')
    try:
        s3.upload_file(local_path, S3_BUCKET, S3_DB_KEY)
        print(f"Uploaded DB from {local_path} to s3://{S3_BUCKET}/{S3_DB_KEY}")
    except Exception as e:
        print(f"S3 upload failed")
        raise


def connect_db(db_file_path):
    # Connect sqlite3
    # detect_types is for date
    conn = sqlite3.connect(db_file_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    c = conn.cursor()

    # Create tables
    c.execute(f'''CREATE TABLE IF NOT EXISTS {KP}
                 (key text PRIMARY KEY, url text, date date, dayid integer, title text, article text, photo integer, chart integer, media text, category text)''')

    c.execute(f'''CREATE TABLE IF NOT EXISTS photo_chart
                 (key text PRIMARY KEY, fkey text REFERENCES {KP} (key), type text, i integer, url text, text text, filename text, url_dbx text)''')
    return conn

# def load_cookies(session):
#     with open(COOKIE_FILE, 'rb') as f:
#         session.cookies = pickle.load(f)

# def save_cookies(session):
#     os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
#     with open(COOKIE_FILE, 'wb') as f:
#         pickle.dump(session.cookies, f)

def login():
    # Access
    s = requests.Session()
    s.headers['Accept-Language'] = 'ja'
    s.headers['User-Agent'] = 'Mozilla/5.0'
    #r = s.get(ROOT_URL)

    # Login
    payload = {
        'mode': 'login',
        'tran': '',
        'ext_login': USR,
        'ext_passwd': PSW   
    }
    r = s.post(ROOT_URL+'/login/', data=payload)

    time.sleep(5)
    soup = BeautifulSoup(r.text, features="html.parser")
    error = soup.find(class_='error_text')
    if (error is not None) and error.get_text().startswith('このアカウントは現在ご利用中です'):
        print("The number of login users exceeds its limitation. Try it again later.")
        sys.exit()
    else:
        # save_cookies(s)
        pass

    return s, r

def get_todays_linklist(s):
    # Get and store contents ==========================    
    # Get links
    try:
        r = s.get(ROOT_URL)
        soup = BeautifulSoup(r.text, features="html.parser")

        articles = []
        # Pickup
        for pickup in soup.find_all(id='home_pickup'):
            link = ROOT_URL + pickup.a.get('href')
            #print(link)
            articles.append(Article(link, category=''))
        # Usual
        for articles_list in soup.find_all(class_='articles_list'):
            for li in articles_list.find_all('li'):
                link = ROOT_URL + li.find('a').get('href')
                #print(link)
                articles.append(Article(link, category=''))
    #except:
    except Exception as e:
        print(e)
        # Logout the page 
        r = s.get(ROOT_URL + '/logout/')

    return articles

def get_articles(s, articles, workdir):
    # Get each page
    try:
        for artcl in articles:
            print(artcl.key)
            artcl.get_article(s, workdir)
            #print(artcl.title)
            time.sleep(1)
    except Exception as e:
        print(e)
    finally:
        # Logout the page 
        r = s.get(ROOT_URL + '/logout/')

    return articles

def store_articles_to_db(articles, c, conn):
    for artcl in articles:
        # Check if data is already existed or not
        c.execute(f"SELECT * FROM {KP} WHERE key=?", (artcl.key,))
        if c.fetchone() == None:
            c.execute(f"INSERT INTO {KP} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", artcl.to_tuple())
    conn.commit()

def upload_photos(articles, workdir, dbx):
    photos = []
    for artcl in articles:
        for i in range(artcl.photo):
            pht = Photo(artcl, i)
            pht.upload_and_get_shared_link(workdir, dbx)
            # os.remove(pht.filename)
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

        self.media = KP
        self.date = ''
        self.dayid = link.split('/')[-2]
        self.key = link

        self.photo = 0
        self.photo_link = []
        self.photo_text = []
        self.chart = 0

    def get_article(self, session, workdir):
        '''Get each page, store in article'''
        r = session.get(self.link)
        self.soup = BeautifulSoup(r.text, features="html.parser")

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
                l = ROOT_URL + p.img['src']
                self.photo_link.append(l)
                self.photo_text.append(t)
                self.get_photo(session, l, workdir)
        #print(self.tpl)

    def get_photo(self, session, link, workdir):
        '''Get photo'''
        r = session.get(link)
        fn = os.path.join(workdir, link.split('/')[-1])
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

    def upload_and_get_shared_link(self, workdir, dbx):
        '''Upload photo and get its shared link'''
        upload_to_dbx(dbx, self.filename, workdir)
        self.link_dbx = get_shared_link_dbx(dbx, self.filename)
        time.sleep(1)
        return self.link_dbx

    def to_tuple(self): 
        '''articles to articletuples (for DB)'''
        tpl = (self.key, self.fkey, self.type, self.i, self.link, self.text, self.filename, self.link_dbx)
        return tpl   

def create_rss(c, file_path):
    # https://feedgen.kiesow.be/index.html
    fg = FeedGenerator()
    fg.id(ROOT_URL)
    fg.title(KPLONG)
    fg.author( {'name':KP,'email':'xxx'} )
    fg.link( href=ROOT_URL, rel='self' )
    fg.language('ja')
    fg.description(KPLONG)

    # Feed entry
    c.execute(f"SELECT * FROM {KP} WHERE date > date('now','-4 days')")
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
    fg.rss_file(file_path)


def main(workdir):
    # Connect DB  =====================================
    conn = connect_db(os.path.join(workdir, DB_FILE))
    c = conn.cursor()

    # Connect DBX  ====================================
    dbx = dropbox.Dropbox(DBX_ACCESS_TOKEN)

    # Access Web and get articles  ====================
    s, r = login()

    articles = get_todays_linklist(s)
    # #articles = articles[:3] ############################
    articles = get_articles(s, articles, workdir)

    # # Store articles into database ==========
    store_articles_to_db(articles, c, conn)

    # # Upload photos and charts. Store the information into photo_chart table
    photos = upload_photos(articles, workdir, dbx)
    store_photos_to_db(photos, c, conn)

    # RSS =============================================
    create_rss(c, os.path.join(workdir, RSS_FILE_NAME))

    # Move the RSS file to destination
    upload_to_dbx(dbx, RSS_FILE_NAME, workdir)
    get_shared_link_dbx(dbx, RSS_FILE_NAME)

    # r = s.get(ROOT_URL + '/logout/')

    # Close =========================================    
    # We can also close the connection if we are done with it.
    # Just be sure any changes have been committed or they will be lost.
    conn.close()

    # return articles
    return None


def upload_to_dbx(dbx, name, workdir, overwrite=True):
    """Upload a file.
    Return the request response, or None in case of error.
    """
    # This script was gotten from sample in official site
    #path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    path_dbx = '/%s' % (name)
    path_local = os.path.join(workdir, name)
    while '//' in path_dbx:
        path_dbx = path_dbx.replace('//', '/')
    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(path_local)
    with open(path_local, 'rb') as f:
        data = f.read()
    try:
        res = dbx.files_upload(
            data, path_dbx, mode,
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


def lambda_handler(event, context):
    workdir = '/tmp'
    local_db_zip_path = os.path.join(workdir, S3_DB_KEY)
    local_db_path = os.path.join(workdir, DB_FILE)
    s3_download_db(local_db_zip_path)
    with zipfile.ZipFile(local_db_zip_path, 'r') as z:
        z.extractall(workdir)

    try:
        articles = main(workdir=workdir)
    except Exception as e:
        print("Error running main:")
        raise

    with zipfile.ZipFile(local_db_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.write(local_db_path, arcname=DB_FILE)
    s3_upload_db(local_db_zip_path)

    return {
        'statusCode': 200,
        'body': f'Successfully processed {len(articles)} articles.'
    }

if __name__ == '__main__':
    main(workdir='.')
