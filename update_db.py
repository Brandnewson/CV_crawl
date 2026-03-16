import psycopg2, os, json, sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r'C:/Code/CV_crawl') / '.env')

meta      = json.loads(open(r'C:/Code/CV_crawl/.cv-apply-meta-tmp.json', encoding='utf-8').read())
docx_path = sys.argv[1]
pdf_path  = sys.argv[2]

conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute(
        "UPDATE job_status SET status = 'cv_generated', status_updated = %s WHERE job_id = %s",
        (datetime.utcnow(), meta['job_id'])
    )
    cur.execute("SELECT id FROM application_packs WHERE job_id = %s", (meta['job_id'],))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE application_packs SET cv_path = %s, cover_letter_path = %s WHERE job_id = %s",
            (docx_path, pdf_path, meta['job_id'])
        )
    else:
        cur.execute(
            "INSERT INTO application_packs (job_id, cv_path, cover_letter_path, created_at) VALUES (%s, %s, %s, %s)",
            (meta['job_id'], docx_path, pdf_path, datetime.utcnow())
        )
conn.commit()
conn.close()
print('DB updated: status -> cv_generated')
