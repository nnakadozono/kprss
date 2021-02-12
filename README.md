# kprss
Check web site and create rss.

## Usage
$ ./run.sh

## SQL
$> sqlite3 yourdbname.db  
sqlite> .schema  
sqlite> select key from tablename limit 20;  
sqlite> select key, url, date, dayid, title, photo, chart from tablename order by date desc limit 50;  
sqlite> .quit  