import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()
client = app.test_client()

with client.session_transaction() as sessao:
    csrf = sessao.get('csrf_token', '')
    print('CSRF token in session:', csrf[:16] + '...' if len(csrf) > 16 else csrf)

res = client.get('/exportar/csv')
print('CSV Content-Type:', res.headers.get('Content-Type'))
print('CSV Content-Disposition:', res.headers.get('Content-Disposition'))
text = res.get_data(as_text=True)
print('CSV starts with BOM:', text[:3] == '\ufeff')
print('CSV has path traversal (..):', '..' in text)
print('CSV line count approx:', text.count(chr(13)+chr(10)))

# Check PDF endpoint
res_pdf = client.get('/exportar/pdf')
print()
print('PDF status:', res_pdf.status_code)
print('PDF body:', res_pdf.get_data(as_text=True)[:100])

# Check headers security on a GET request
res_home = client.get('/')
print()
print('CSP:', res_home.headers.get('Content-Security-Policy'))
print('X-Frame-Options:', res_home.headers.get('X-Frame-Options'))
print('X-Content-Type-Options:', res_home.headers.get('X-Content-Type-Options'))
print('Referrer-Policy:', res_home.headers.get('Referrer-Policy'))
print('Permissions-Policy:', res_home.headers.get('Permissions-Policy'))
print('Session Cookie HttpOnly:', res_home.headers.get('Set-Cookie', '').find('HttpOnly') >= 0)
print('Session Cookie SameSite:', res_home.headers.get('Set-Cookie', '').find('SameSite') >= 0)